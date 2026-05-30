"""Tests for census_search.linker."""

import pytest

from census_search.linker import AGE_TOLERANCE, _is_likely_match, _names_match, link_person, score_match
from census_search.models import CensusRecord, SearchResult

# ---------------------------------------------------------------------------
# _names_match
# ---------------------------------------------------------------------------

class TestNamesMatch:
    def test_exact_match(self):
        assert _names_match("Murphy", "Murphy")

    def test_case_insensitive(self):
        assert _names_match("MURPHY", "murphy")
        assert _names_match("murphy", "MURPHY")

    def test_prefix_short_to_long(self):
        # "Pat" is prefix of "Patrick"
        assert _names_match("Pat", "Patrick")

    def test_prefix_long_to_short(self):
        assert _names_match("Patrick", "Pat")

    def test_different_names(self):
        assert not _names_match("Murphy", "Brien")

    def test_empty_a(self):
        # Empty string → treat as unknown → True
        assert _names_match("", "Murphy")

    def test_empty_b(self):
        assert _names_match("Murphy", "")

    def test_both_empty(self):
        assert _names_match("", "")

    def test_whitespace_stripped(self):
        assert _names_match("  Murphy  ", "Murphy")

    def test_prefix_substring(self):
        # "Mur" IS a string-prefix of "Murphy" so matches
        assert _names_match("Mur", "Murphy")

    def test_completely_different(self):
        assert not _names_match("Corrigan", "Murphy")

    def test_similar_but_not_prefix(self):
        assert not _names_match("James", "John")

    def test_single_char(self):
        # "J" is prefix of "James"
        assert _names_match("J", "James")


# ---------------------------------------------------------------------------
# _is_likely_match
# ---------------------------------------------------------------------------

class TestIsLikelyMatch:
    def _make(self, year, surname, first_name="", age=None, sex=""):
        return CensusRecord(
            census_year=year, surname=surname, first_name=first_name,
            age=age, sex=sex,
        )

    def test_exact_match_all_fields(self):
        anchor = self._make(1926, "Corrigan", "James", age=46, sex="Male")
        candidate = self._make(1911, "Corrigan", "James", age=31, sex="Male")
        assert _is_likely_match(anchor, candidate, birth_year=1880)

    def test_surname_mismatch(self):
        anchor = self._make(1926, "Corrigan", "James", age=46)
        candidate = self._make(1911, "Murphy", "James", age=31)
        assert not _is_likely_match(anchor, candidate, birth_year=1880)

    def test_first_name_mismatch(self):
        anchor = self._make(1926, "Corrigan", "James", age=46)
        candidate = self._make(1911, "Corrigan", "Mary", age=31)
        assert not _is_likely_match(anchor, candidate, birth_year=1880)

    def test_age_outside_tolerance(self):
        anchor = self._make(1926, "Corrigan", "James", age=46)
        # birth year from anchor = 1880; candidate birth year = 1901-10 = 1891 → diff=11
        candidate = self._make(1901, "Corrigan", "James", age=10)
        assert not _is_likely_match(anchor, candidate, birth_year=1880)

    def test_age_within_tolerance(self):
        anchor = self._make(1926, "Corrigan", "James", age=46)
        # candidate birth year = 1901-23 = 1878 → diff=2
        candidate = self._make(1901, "Corrigan", "James", age=23)
        assert _is_likely_match(anchor, candidate, birth_year=1880)

    def test_sex_mismatch(self):
        anchor = self._make(1926, "Corrigan", "James", age=46, sex="Male")
        candidate = self._make(1911, "Corrigan", "James", age=31, sex="Female")
        assert not _is_likely_match(anchor, candidate, birth_year=1880)

    def test_sex_case_insensitive(self):
        anchor = self._make(1926, "Corrigan", "James", age=46, sex="male")
        candidate = self._make(1911, "Corrigan", "James", age=31, sex="MALE")
        assert _is_likely_match(anchor, candidate, birth_year=1880)

    def test_no_birth_year_skips_age_check(self):
        anchor = self._make(1926, "Corrigan", "James")
        candidate = self._make(1911, "Corrigan", "James", age=5)
        # No birth_year supplied → age check skipped → still matches on name
        assert _is_likely_match(anchor, candidate, birth_year=None)

    def test_no_candidate_age_skips_age_check(self):
        anchor = self._make(1926, "Corrigan", "James", age=46)
        candidate = self._make(1911, "Corrigan", "James")  # no age
        assert _is_likely_match(anchor, candidate, birth_year=1880)

    def test_abbreviated_first_name_no_prefix_match(self):
        # "Jas" is a common abbreviation but NOT a string-prefix of "James"
        # (j-a-s vs j-a-m-e-s), so _names_match correctly returns False here.
        anchor = self._make(1926, "Corrigan", "James", age=46)
        candidate = self._make(1911, "Corrigan", "Jas", age=31)
        assert not _is_likely_match(anchor, candidate, birth_year=1880)

    def test_empty_first_names(self):
        anchor = self._make(1926, "Corrigan", "", age=46)
        candidate = self._make(1911, "Corrigan", "", age=31)
        assert _is_likely_match(anchor, candidate, birth_year=1880)

    def test_boundary_tolerance_exact(self):
        anchor = self._make(1926, "X", age=46)           # birth=1880
        candidate = self._make(1901, "X", age=21 - AGE_TOLERANCE)  # birth=1880+AGE_TOLERANCE
        assert _is_likely_match(anchor, candidate, birth_year=1880)

    def test_boundary_tolerance_exceeded(self):
        anchor = self._make(1926, "X", age=46)   # birth=1880
        # candidate birth = 1901 - (21 - AGE_TOLERANCE - 1) = 1880 + AGE_TOLERANCE + 1
        bad_age = 21 - AGE_TOLERANCE - 1
        candidate = self._make(1901, "X", age=bad_age)
        assert not _is_likely_match(anchor, candidate, birth_year=1880)


# ---------------------------------------------------------------------------
# score_match
# ---------------------------------------------------------------------------

class TestScoreMatch:
    def _make(self, year, surname, first_name="", age=None, sex="", county=""):
        return CensusRecord(
            census_year=year, surname=surname, first_name=first_name,
            age=age, sex=sex, county=county,
        )

    def test_perfect_match_score_is_one(self):
        a = self._make(1926, "Corrigan", "James", age=46, sex="Male", county="Kilkenny")
        b = self._make(1911, "Corrigan", "James", age=31, sex="Male", county="Kilkenny")
        score = score_match(a, b)
        assert score == pytest.approx(1.0)

    def test_no_fields_returns_zero(self):
        a = CensusRecord(census_year=1926)
        b = CensusRecord(census_year=1911)
        assert score_match(a, b) == pytest.approx(0.0)

    def test_surname_only_exact(self):
        a = self._make(1926, "Murphy")
        b = self._make(1911, "Murphy")
        score = score_match(a, b)
        assert score == pytest.approx(1.0)

    def test_surname_wrong(self):
        a = self._make(1926, "Murphy")
        b = self._make(1911, "Brien")
        score = score_match(a, b)
        assert score == pytest.approx(0.0)

    def test_score_range(self):
        a = self._make(1926, "Corrigan", "James", age=46, sex="Male", county="Kilkenny")
        b = self._make(1911, "Corrigan", "Mary", age=31, sex="Female", county="Cork")
        score = score_match(a, b)
        assert 0.0 <= score <= 1.0

    def test_partial_first_name_lower_than_exact(self):
        a = self._make(1926, "Murphy", "Patrick", age=40)
        exact = self._make(1911, "Murphy", "Patrick", age=25)
        approx_ = self._make(1911, "Murphy", "Pat", age=25)
        assert score_match(a, exact) > score_match(a, approx_)

    def test_age_diff_zero_scores_higher_than_diff_two(self):
        anchor = self._make(1926, "Murphy", age=46)  # birth=1880
        exact_age = self._make(1911, "Murphy", age=31)   # birth=1880
        off_by_two = self._make(1911, "Murphy", age=29)  # birth=1882
        assert score_match(anchor, exact_age) > score_match(anchor, off_by_two)

    def test_county_bonus(self):
        anchor = self._make(1926, "Murphy", county="Dublin")
        same_county = self._make(1911, "Murphy", county="Dublin")
        diff_county = self._make(1911, "Murphy", county="Cork")
        assert score_match(anchor, same_county) > score_match(anchor, diff_county)


# ---------------------------------------------------------------------------
# link_person
# ---------------------------------------------------------------------------

class TestLinkPerson:
    def test_links_matching_records(self, record_1926, result_1911, result_1901):
        linked = link_person(record_1926, [result_1911, result_1901])
        assert len(linked.records) == 3
        assert linked.census_years == [1901, 1911, 1926]

    def test_name_from_anchor(self, record_1926, result_1911, result_1901):
        linked = link_person(record_1926, [result_1911, result_1901])
        assert linked.name == "James Corrigan"

    def test_no_older_results(self, record_1926):
        linked = link_person(record_1926, [])
        assert len(linked.records) == 1
        assert linked.census_years == [1926]

    def test_non_matching_candidates_excluded(self, record_1926):
        wrong = CensusRecord(
            census_year=1911, surname="Murphy", first_name="Patrick",
            age=40, sex="Male",
        )
        result = SearchResult(census_year=1911, total=1, records=[wrong])
        linked = link_person(record_1926, [result])
        assert len(linked.records) == 1  # Only the 1926 anchor

    def test_only_best_match_per_year(self, record_1926):
        """Only first matching record per census year is taken."""
        r1 = CensusRecord(census_year=1911, surname="Corrigan", first_name="James", age=31)
        r2 = CensusRecord(census_year=1911, surname="Corrigan", first_name="James", age=30)
        result = SearchResult(census_year=1911, total=2, records=[r1, r2])
        linked = link_person(record_1926, [result])
        assert len(linked.records) == 2  # anchor + first match

    def test_empty_older_results(self, record_1926):
        empty = SearchResult(census_year=1911, total=0, records=[])
        linked = link_person(record_1926, [empty])
        assert len(linked.records) == 1

    def test_mixed_match_and_no_match(self, record_1926, result_1911):
        no_match = SearchResult(
            census_year=1901, total=1,
            records=[CensusRecord(census_year=1901, surname="Murphy", first_name="John", age=10)],
        )
        linked = link_person(record_1926, [result_1911, no_match])
        assert len(linked.records) == 2
        assert 1911 in linked.census_years
        assert 1901 not in linked.census_years
