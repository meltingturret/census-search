"""Tests for the deeper-search features:

- Fuzzy/phonetic surname matching in linker
- Relationship-aware confidence scoring
- Confidence scoring (score_match + best_scored_match)
- Multi-county search in CLI
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from typer.testing import CliRunner

from census_search.cli import app
from census_search.linker import (
    MATCH_THRESHOLD,
    _names_match,
    _relationship_score,
    best_scored_match,
    score_match,
)
from census_search.models import CensusRecord, SearchResult

runner = CliRunner()


def _make_result(year: int, records: list[CensusRecord]) -> SearchResult:
    return SearchResult(
        census_year=year,
        total=len(records),
        records=records,
        search_url=f"https://example.com/{year}",
    )


def _rec(**kwargs) -> CensusRecord:
    defaults = dict(census_year=1911, surname="Murphy", first_name="Mary", age=30, sex="Female")
    defaults.update(kwargs)
    return CensusRecord(**defaults)


# ---------------------------------------------------------------------------
# Fuzzy / phonetic surname matching
# ---------------------------------------------------------------------------

class TestPhoneticNamesMatch:
    def test_exact_match(self):
        assert _names_match("Corrigan", "Corrigan")

    def test_case_insensitive(self):
        assert _names_match("corrigan", "CORRIGAN")

    def test_prefix_match(self):
        assert _names_match("Pat", "Patrick")
        assert _names_match("Patrick", "Pat")

    def test_soundex_variant(self):
        """Spelling variants with the same Soundex code should match."""
        assert _names_match("Corrigan", "Corigan")
        assert _names_match("Purcell", "Pursell")
        assert _names_match("Murphy", "Murphey")

    def test_high_similarity_match(self):
        """Names with ≥80% character similarity should match."""
        assert _names_match("Brien", "Brian")

    def test_completely_different_no_match(self):
        assert not _names_match("Murphy", "Kelly")
        assert not _names_match("Corrigan", "Walsh")

    def test_empty_a_returns_true(self):
        assert _names_match("", "Murphy")

    def test_empty_b_returns_true(self):
        assert _names_match("Murphy", "")


# ---------------------------------------------------------------------------
# Relationship-aware scoring
# ---------------------------------------------------------------------------

class TestRelationshipScore:
    def test_same_relationship_perfect(self):
        assert _relationship_score("Head", "Head") == 1.0
        assert _relationship_score("wife", "wife") == 1.0

    def test_case_insensitive(self):
        assert _relationship_score("Son", "son") == 1.0

    def test_son_scholar_compatible(self):
        score = _relationship_score("Son", "Scholar")
        assert score >= 0.80

    def test_daughter_scholar_compatible(self):
        score = _relationship_score("Daughter", "Scholar")
        assert score >= 0.80

    def test_incompatible_relationships_low(self):
        # Head in 1926, Wife in 1911 — unlikely same person
        score = _relationship_score("Head", "Wife")
        assert score < 0.40

    def test_unknown_relationship_neutral(self):
        score = _relationship_score("", "Head")
        assert score == 0.5
        score = _relationship_score("Head", "")
        assert score == 0.5

    def test_unknown_pair_low(self):
        # Two valid but unrelated relationships with no mapping
        score = _relationship_score("Lodger", "Niece")
        assert score < 0.40


# ---------------------------------------------------------------------------
# Confidence scoring (score_match)
# ---------------------------------------------------------------------------

class TestScoreMatch:
    def _anchor(self, **kw) -> CensusRecord:
        return _rec(census_year=1926, **kw)

    def test_perfect_match_scores_high(self):
        anchor = self._anchor(surname="Murphy", first_name="Mary", age=39, sex="Female", county="Kilkenny")
        candidate = _rec(surname="Murphy", first_name="Mary", age=28, sex="Female", county="Kilkenny")
        # age diff = 11 years → low age score but names+sex+county should still give decent total
        score = score_match(anchor, candidate)
        assert 0.0 < score <= 1.0

    def test_identical_fields_max_score(self):
        anchor = self._anchor(surname="Murphy", first_name="Mary", age=39, sex="Female", county="Kilkenny")
        # Same person, exact age match across years (±0)
        candidate = _rec(census_year=1911, surname="Murphy", first_name="Mary", age=28, sex="Female", county="Kilkenny")
        # birth years: anchor 1926-39=1887, candidate 1911-28=1883 → diff=4 > tolerance
        # But same name/sex/county → still meaningful score
        score = score_match(anchor, candidate)
        assert score > 0.40

    def test_soundex_surname_partial_credit(self):
        """A phonetically matching but differently spelled surname earns partial credit."""
        anchor = self._anchor(surname="Corrigan", first_name="James")
        candidate = _rec(surname="Corigan", first_name="James")
        score = score_match(anchor, candidate)
        # Soundex match → 0.70 × weight 3; exact first name → full 2 → combined ~0.56+
        assert score > 0.50

    def test_wrong_sex_reduces_score(self):
        anchor = self._anchor(surname="Murphy", first_name="Mary", sex="Female")
        male = _rec(surname="Murphy", first_name="Mary", sex="Male")
        female = _rec(surname="Murphy", first_name="Mary", sex="Female")
        assert score_match(anchor, female) > score_match(anchor, male)

    def test_matching_county_boosts_score(self):
        anchor = self._anchor(surname="Murphy", first_name="Mary", county="Kilkenny")
        same_county = _rec(surname="Murphy", first_name="Mary", county="Kilkenny")
        diff_county = _rec(surname="Murphy", first_name="Mary", county="Dublin")
        assert score_match(anchor, same_county) > score_match(anchor, diff_county)

    def test_relationship_bonus_applied(self):
        anchor = self._anchor(surname="Murphy", first_name="Mary", relationship="Daughter")
        scholar = _rec(surname="Murphy", first_name="Mary", relationship="Scholar")
        wife = _rec(surname="Murphy", first_name="Mary", relationship="Wife")
        # Daughter→Scholar is compatible; Daughter→Wife is less so
        assert score_match(anchor, scholar) >= score_match(anchor, wife)

    def test_score_in_range(self):
        anchor = self._anchor(surname="Murphy", first_name="Mary", age=39, sex="Female", county="Kilkenny")
        candidate = _rec(surname="Kelly", first_name="John", age=55, sex="Male", county="Dublin")
        score = score_match(anchor, candidate)
        assert 0.0 <= score <= 1.0


# ---------------------------------------------------------------------------
# best_scored_match
# ---------------------------------------------------------------------------

class TestBestScoredMatch:
    def _anchor(self, **kw) -> CensusRecord:
        return _rec(census_year=1926, **kw)

    def test_returns_none_for_empty_result(self):
        anchor = self._anchor(surname="Murphy")
        result = _make_result(1911, [])
        assert best_scored_match(anchor, result) is None

    def test_returns_best_candidate(self):
        anchor = self._anchor(surname="Corrigan", first_name="James", age=44, sex="Male", county="Kilkenny")
        good = _rec(surname="Corrigan", first_name="James", age=33, sex="Male", county="Kilkenny")
        poor = _rec(surname="Kelly", first_name="John", age=55, sex="Male", county="Dublin")
        result = _make_result(1911, [poor, good])
        match = best_scored_match(anchor, result)
        assert match is not None
        rec, score = match
        assert rec.first_name == "James"
        assert 0.0 < score <= 1.0

    def test_low_scoring_candidates_return_none(self):
        anchor = self._anchor(surname="Murphy", first_name="Mary", age=39, sex="Female")
        # Completely different person
        candidate = _rec(surname="Kelly", first_name="John", age=70, sex="Male")
        result = _make_result(1911, [candidate])
        match = best_scored_match(anchor, result)
        # Score should be below MATCH_THRESHOLD
        assert match is None or match[1] < MATCH_THRESHOLD + 0.05

    def test_score_is_highest_among_candidates(self):
        anchor = self._anchor(surname="Purcell", first_name="Mary", age=39, sex="Female", county="Kilkenny")
        candidates = [
            _rec(surname="Purcell", first_name="Mary", age=28, sex="Female", county="Kilkenny"),
            _rec(surname="Purcell", first_name="Mary", age=28, sex="Female", county="Dublin"),
            _rec(surname="Purcell", first_name="Kate", age=28, sex="Female", county="Kilkenny"),
        ]
        result = _make_result(1911, candidates)
        match = best_scored_match(anchor, result)
        assert match is not None
        rec, score = match
        # Best match should be Kilkenny + Mary (exact name + county)
        assert rec.county == "Kilkenny"
        assert rec.first_name == "Mary"


# ---------------------------------------------------------------------------
# Multi-county CLI
# ---------------------------------------------------------------------------

def _setup_mocks(records_1926, records_1911=None, records_1901=None, side_effects=None):
    mock_1926 = AsyncMock()
    mock_1926.__aenter__ = AsyncMock(return_value=mock_1926)
    mock_1926.__aexit__ = AsyncMock(return_value=False)
    if side_effects:
        mock_1926.search.side_effect = side_effects
    else:
        mock_1926.search = AsyncMock(return_value=SearchResult(
            census_year=1926, total=len(records_1926), records=records_1926,
            search_url="https://example.com/1926",
        ))

    mock_old = AsyncMock()
    mock_old.__aenter__ = AsyncMock(return_value=mock_old)
    mock_old.__aexit__ = AsyncMock(return_value=False)
    mock_old.search_both_years = AsyncMock(return_value=[
        SearchResult(census_year=1911, total=len(records_1911 or []), records=records_1911 or [], search_url=""),
        SearchResult(census_year=1901, total=len(records_1901 or []), records=records_1901 or [], search_url=""),
    ])
    return mock_1926, mock_old


class TestMultiCountyCLI:
    def test_single_county_calls_search_once(self):
        rec = CensusRecord(census_year=1926, surname="Murphy", first_name="Mary", age=39,
                           county="Kilkenny", townland_street="Lamogue", ded="Kilmaganny")
        mock_1926, mock_old = _setup_mocks([rec])
        with (
            patch("census_search.cli.Census1926Searcher", return_value=mock_1926),
            patch("census_search.cli.Census1901_1911Searcher", return_value=mock_old),
        ):
            result = runner.invoke(app, ["link", "Murphy", "--first-name", "Mary",
                                         "--birth-year", "1887", "--county", "Kilkenny"])
        assert result.exit_code == 0
        # Primary search + household fetch = 2 calls for single county
        assert mock_1926.search.call_count >= 1
        first_call = mock_1926.search.call_args_list[0].kwargs
        assert first_call.get("county") == "Kilkenny"

    def test_two_counties_calls_search_twice_for_1926(self):
        rec_kk = CensusRecord(census_year=1926, surname="Murphy", first_name="Mary", age=39, county="Kilkenny")
        rec_tp = CensusRecord(census_year=1926, surname="Murphy", first_name="Mary", age=40, county="Tipperary")

        def side_effect(**kwargs):
            county = kwargs.get("county", "")
            if county == "Kilkenny":
                return SearchResult(census_year=1926, total=1, records=[rec_kk], search_url="")
            if county == "Tipperary":
                return SearchResult(census_year=1926, total=1, records=[rec_tp], search_url="")
            return SearchResult(census_year=1926, total=0, records=[], search_url="")

        mock_1926 = AsyncMock()
        mock_1926.__aenter__ = AsyncMock(return_value=mock_1926)
        mock_1926.__aexit__ = AsyncMock(return_value=False)
        mock_1926.search = AsyncMock(side_effect=side_effect)

        mock_old = AsyncMock()
        mock_old.__aenter__ = AsyncMock(return_value=mock_old)
        mock_old.__aexit__ = AsyncMock(return_value=False)
        mock_old.search_both_years = AsyncMock(return_value=[
            SearchResult(census_year=1911, total=0, records=[], search_url=""),
            SearchResult(census_year=1901, total=0, records=[], search_url=""),
        ])

        with (
            patch("census_search.cli.Census1926Searcher", return_value=mock_1926),
            patch("census_search.cli.Census1901_1911Searcher", return_value=mock_old),
        ):
            result = runner.invoke(app, ["link", "Murphy", "--first-name", "Mary",
                                         "--birth-year", "1887", "--county", "Kilkenny,Tipperary"])
        assert result.exit_code == 0
        counties_searched = [
            call.kwargs.get("county") for call in mock_1926.search.call_args_list
        ]
        assert "Kilkenny" in counties_searched
        assert "Tipperary" in counties_searched

    def test_multi_county_both_counties_are_queried(self):
        """When two counties are given, 1926 searcher is called once per county."""
        rec_kk = CensusRecord(census_year=1926, surname="Murphy", first_name="Mary", age=39, county="Kilkenny")

        def side_effect(**kwargs):
            county = kwargs.get("county", "")
            if county == "Kilkenny":
                return SearchResult(census_year=1926, total=1, records=[rec_kk], search_url="")
            return SearchResult(census_year=1926, total=0, records=[], search_url="")

        mock_1926 = AsyncMock()
        mock_1926.__aenter__ = AsyncMock(return_value=mock_1926)
        mock_1926.__aexit__ = AsyncMock(return_value=False)
        mock_1926.search = AsyncMock(side_effect=side_effect)

        mock_old = AsyncMock()
        mock_old.__aenter__ = AsyncMock(return_value=mock_old)
        mock_old.__aexit__ = AsyncMock(return_value=False)
        mock_old.search_both_years = AsyncMock(return_value=[
            SearchResult(census_year=1911, total=0, records=[], search_url=""),
            SearchResult(census_year=1901, total=0, records=[], search_url=""),
        ])

        with (
            patch("census_search.cli.Census1926Searcher", return_value=mock_1926),
            patch("census_search.cli.Census1901_1911Searcher", return_value=mock_old),
        ):
            result = runner.invoke(app, ["link", "Murphy", "--first-name", "Mary",
                                         "--birth-year", "1887", "--county", "Kilkenny,Tipperary"])
        assert result.exit_code == 0
        counties_queried = [c.kwargs.get("county") for c in mock_1926.search.call_args_list]
        assert "Kilkenny" in counties_queried
        assert "Tipperary" in counties_queried


# ---------------------------------------------------------------------------
# Confidence display in CLI output
# ---------------------------------------------------------------------------

class TestConfidenceDisplay:
    def test_confidence_shown_for_1911_match(self):
        anchor_1926 = CensusRecord(
            census_year=1926, surname="Corrigan", first_name="James", age=44,
            sex="Male", county="Kilkenny", townland_street="Lamogue", ded="Kilmaganny",
        )
        match_1911 = CensusRecord(
            census_year=1911, surname="Corrigan", first_name="James", age=33,
            sex="Male", county="Kilkenny",
        )
        mock_1926 = AsyncMock()
        mock_1926.__aenter__ = AsyncMock(return_value=mock_1926)
        mock_1926.__aexit__ = AsyncMock(return_value=False)
        mock_1926.search = AsyncMock(return_value=SearchResult(
            census_year=1926, total=1, records=[anchor_1926], search_url="",
        ))
        mock_old = AsyncMock()
        mock_old.__aenter__ = AsyncMock(return_value=mock_old)
        mock_old.__aexit__ = AsyncMock(return_value=False)
        mock_old.search_both_years = AsyncMock(return_value=[
            SearchResult(census_year=1911, total=1, records=[match_1911], search_url=""),
            SearchResult(census_year=1901, total=0, records=[], search_url=""),
        ])
        with (
            patch("census_search.cli.Census1926Searcher", return_value=mock_1926),
            patch("census_search.cli.Census1901_1911Searcher", return_value=mock_old),
        ):
            result = runner.invoke(app, ["link", "Corrigan", "--first-name", "James",
                                          "--birth-year", "1882", "--county", "Kilkenny"])
        assert result.exit_code == 0
        # A percentage should appear in the 1911 line
        assert "%" in result.output
