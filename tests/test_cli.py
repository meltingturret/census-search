"""Tests for the CLI layer (no browser, mocked searchers)."""

from __future__ import annotations

import re
from unittest.mock import AsyncMock, patch

from typer.testing import CliRunner

from census_search.cli import app
from census_search.models import CensusRecord, MilitaryRecord, SearchResult

runner = CliRunner(env={"NO_COLOR": "1"})


def _plain(text: str) -> str:
    """Strip ANSI escape codes for reliable string assertions."""
    return re.sub(r"\x1b\[[0-9;]*[mGKHF]", "", text)


def _make_result(year: int, records: list[CensusRecord], total: int | None = None) -> SearchResult:
    return SearchResult(
        census_year=year,
        total=total if total is not None else len(records),
        records=records,
        search_url=f"https://example.com/{year}",
    )


def _corrigan_1926() -> CensusRecord:
    return CensusRecord(
        census_year=1926, surname="Corrigan", first_name="James",
        age=46, sex="Male", county="Kilkenny",
        townland_street="Lamogue", ded="Kilmaganny",
    )


# ---------------------------------------------------------------------------
# --help
# ---------------------------------------------------------------------------

class TestHelpOutput:
    def test_root_help(self):
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "link" in result.output
        assert "browse" in result.output

    def test_no_args_shows_help(self):
        result = runner.invoke(app, [])
        assert result.exit_code == 0
        assert "link" in result.output
        assert "Usage" in result.output

    def test_link_help(self):
        result = runner.invoke(app, ["link", "--help"])
        assert result.exit_code == 0
        out = _plain(result.output)
        assert "--birth-year" in out
        assert "--first-name" in out
        assert "--county" in out
        assert "--sex" in out
        assert "--service-number" in out

    def test_browse_help(self):
        result = runner.invoke(app, ["browse", "--help"])
        assert result.exit_code == 0
        assert "--county" in _plain(result.output)


# ---------------------------------------------------------------------------
# link command
# ---------------------------------------------------------------------------

def _setup_link_mocks(records_1926, records_1911=None, records_1901=None):
    mock_1926 = AsyncMock()
    mock_1926.__aenter__ = AsyncMock(return_value=mock_1926)
    mock_1926.__aexit__ = AsyncMock(return_value=False)
    mock_1926.search = AsyncMock(return_value=_make_result(1926, records_1926))

    mock_old = AsyncMock()
    mock_old.__aenter__ = AsyncMock(return_value=mock_old)
    mock_old.__aexit__ = AsyncMock(return_value=False)
    mock_old.search_both_years = AsyncMock(return_value=[
        _make_result(1911, records_1911 or []),
        _make_result(1901, records_1901 or []),
    ])

    return mock_1926, mock_old


class TestLinkCommand:
    def test_exits_0_with_results(self):
        mock_1926, mock_old = _setup_link_mocks([_corrigan_1926()])
        with (
            patch("census_search.cli.Census1926Searcher", return_value=mock_1926),
            patch("census_search.cli.Census1901_1911Searcher", return_value=mock_old),
        ):
            result = runner.invoke(app, ["link", "Corrigan", "--birth-year", "1880"])
        assert result.exit_code == 0

    def test_birth_year_optional(self):
        """--birth-year is now optional; omitting it should still exit 0."""
        mock_1926, mock_old = _setup_link_mocks([_corrigan_1926()])
        with (
            patch("census_search.cli.Census1926Searcher", return_value=mock_1926),
            patch("census_search.cli.Census1901_1911Searcher", return_value=mock_old),
        ):
            result = runner.invoke(app, ["link", "Corrigan", "--county", "Kilkenny"])
        assert result.exit_code == 0

    def test_no_birth_year_skips_1911_1901_search(self):
        """Without --birth-year, 1901/1911 search is not performed."""
        mock_1926, mock_old = _setup_link_mocks([_corrigan_1926()])
        with (
            patch("census_search.cli.Census1926Searcher", return_value=mock_1926),
            patch("census_search.cli.Census1901_1911Searcher", return_value=mock_old),
        ):
            runner.invoke(app, ["link", "Corrigan", "--county", "Kilkenny"])
        mock_old.search_both_years.assert_not_called()

    def test_multiple_matches_no_birth_year_shows_table(self):
        """Multiple 1926 matches without --birth-year show a results table, not a single-row tree."""
        rec1 = CensusRecord(census_year=1926, surname="Corrigan", first_name="James", age=44,
                            county="Kilkenny", townland_street="Lamogue", ded="Kilmaganny")
        rec2 = CensusRecord(census_year=1926, surname="Corrigan", first_name="Patrick", age=52,
                            county="Kilkenny", townland_street="Main Street", ded="Kilkenny Urban")
        mock_1926, mock_old = _setup_link_mocks([rec1, rec2])
        with (
            patch("census_search.cli.Census1926Searcher", return_value=mock_1926),
            patch("census_search.cli.Census1901_1911Searcher", return_value=mock_old),
        ):
            result = runner.invoke(app, ["link", "Corrigan", "--county", "Kilkenny"])
        assert result.exit_code == 0
        # Header shows result count and hint
        assert "2 result" in result.output
        assert "result" in result.output
        # Tree-style year markers should NOT appear (table mode, not tree mode)
        assert "├──" not in result.output
        # 1901/1911 not searched
        mock_old.search_both_years.assert_not_called()

    def test_shows_surname_in_output(self):
        mock_1926, mock_old = _setup_link_mocks([_corrigan_1926()])
        with (
            patch("census_search.cli.Census1926Searcher", return_value=mock_1926),
            patch("census_search.cli.Census1901_1911Searcher", return_value=mock_old),
        ):
            result = runner.invoke(app, ["link", "Corrigan", "--birth-year", "1880"])
        assert "Corrigan" in result.output

    def test_shows_years_with_results(self):
        mock_1926, mock_old = _setup_link_mocks(
            [_corrigan_1926()],
            records_1911=[CensusRecord(census_year=1911, surname="Corrigan", age=31)],
        )
        with (
            patch("census_search.cli.Census1926Searcher", return_value=mock_1926),
            patch("census_search.cli.Census1901_1911Searcher", return_value=mock_old),
        ):
            result = runner.invoke(app, ["link", "Corrigan", "--birth-year", "1880"])
        assert "1926" in result.output
        assert "1911" in result.output
        # 1901 has 0 results so is omitted from the summary

    def test_sex_filters_client_side(self):
        """Female records are excluded when --sex Male is given, regardless of API response."""
        male1 = CensusRecord(census_year=1926, surname="Corrigan", first_name="James",
                             age=44, sex="Male", county="Kilkenny",
                             townland_street="Lamogue", ded="Kilmaganny")
        male2 = CensusRecord(census_year=1926, surname="Corrigan", first_name="Patrick",
                             age=52, sex="Male", county="Kilkenny",
                             townland_street="Main Street", ded="Kilkenny Urban")
        female_rec = CensusRecord(census_year=1926, surname="Corrigan", first_name="Mary",
                                  age=39, sex="Female", county="Kilkenny",
                                  townland_street="Lamogue", ded="Kilmaganny")
        # API returns all three; with no birth year and 2+ results the table path is used
        # (no household fetch), so only matched records appear in output
        mock_1926, mock_old = _setup_link_mocks([male1, male2, female_rec])
        with (
            patch("census_search.cli.Census1926Searcher", return_value=mock_1926),
            patch("census_search.cli.Census1901_1911Searcher", return_value=mock_old),
        ):
            result = runner.invoke(app, ["link", "Corrigan", "--sex", "Male"])
        assert result.exit_code == 0
        assert "2 result" in result.output   # only the two males matched
        assert "Female" not in result.output

    def test_sex_filter_keeps_records_with_unknown_sex(self):
        """Records with no sex data are kept when --sex is given (can't confirm a conflict)."""
        no_sex_rec = CensusRecord(
            census_year=1926, surname="Corrigan", first_name="James", age=44,
            sex="", county="Kilkenny", townland_street="Lamogue", ded="Kilmaganny",
        )
        mock_1926, mock_old = _setup_link_mocks([no_sex_rec])
        with (
            patch("census_search.cli.Census1926Searcher", return_value=mock_1926),
            patch("census_search.cli.Census1901_1911Searcher", return_value=mock_old),
        ):
            result = runner.invoke(app, ["link", "Corrigan", "--birth-year", "1882", "--sex", "Male"])
        assert result.exit_code == 0
        assert " 44 " in result.output  # record was not dropped due to missing sex

    def test_sex_passed_to_searcher(self):
        mock_1926, mock_old = _setup_link_mocks([_corrigan_1926()])
        with (
            patch("census_search.cli.Census1926Searcher", return_value=mock_1926),
            patch("census_search.cli.Census1901_1911Searcher", return_value=mock_old),
        ):
            runner.invoke(app, ["link", "Corrigan", "--birth-year", "1880", "--sex", "Male"])
        # First call is the primary search; second is the household fetch (no sex param)
        first_call_kwargs = mock_1926.search.call_args_list[0].kwargs
        assert first_call_kwargs.get("sex") == "Male"

    def test_single_match_fetches_household(self):
        """A single 1926 match triggers an automatic household fetch."""
        mock_1926, mock_old = _setup_link_mocks([_corrigan_1926()])
        with (
            patch("census_search.cli.Census1926Searcher", return_value=mock_1926),
            patch("census_search.cli.Census1901_1911Searcher", return_value=mock_old),
        ):
            runner.invoke(app, ["link", "Corrigan", "--birth-year", "1880"])
        # search called twice: primary search + household fetch
        assert mock_1926.search.call_count == 2

    def test_multiple_matches_no_household_fetch(self):
        """Multiple distinct 1926 matches do not trigger household fetch."""
        rec1 = CensusRecord(census_year=1926, surname="Corrigan", first_name="James",
                            age=46, sex="Male", county="Kilkenny",
                            townland_street="Lamogue", ded="Kilmaganny")
        rec2 = CensusRecord(census_year=1926, surname="Corrigan", first_name="James",
                            age=48, sex="Male", county="Tipperary",
                            townland_street="Main Street", ded="Clonmel")
        mock_1926, mock_old = _setup_link_mocks([rec1, rec2])
        with (
            patch("census_search.cli.Census1926Searcher", return_value=mock_1926),
            patch("census_search.cli.Census1901_1911Searcher", return_value=mock_old),
        ):
            runner.invoke(app, ["link", "Corrigan", "--birth-year", "1880"])
        assert mock_1926.search.call_count == 1

    def test_no_1926_match_shows_no_match(self):
        """When no 1926 records pass the filter, no record data is displayed for 1926."""
        mock_1926, mock_old = _setup_link_mocks([])
        with (
            patch("census_search.cli.Census1926Searcher", return_value=mock_1926),
            patch("census_search.cli.Census1901_1911Searcher", return_value=mock_old),
        ):
            result = runner.invoke(app, ["link", "Gilligan", "--first-name", "Fred", "--birth-year", "1882"])
        assert result.exit_code == 0
        assert "1926" in result.output
        # The synthetic age (44) should never appear — no real record was matched
        assert " 44 " not in result.output

    def test_household_members_always_linked(self):
        """Household members are always linked to 1911/1901 — no --expand needed."""
        household = [
            CensusRecord(census_year=1926, surname="Corrigan", first_name="Mary", age=39,
                         sex="Female", county="Kilkenny", townland_street="Lamogue", ded="Kilmaganny"),
        ]
        mock_1926, mock_old = _setup_link_mocks([_corrigan_1926()])
        mock_1926.search.side_effect = [
            _make_result(1926, [_corrigan_1926()]),  # primary search
            _make_result(1926, household),            # household fetch
        ]
        with (
            patch("census_search.cli.Census1926Searcher", return_value=mock_1926),
            patch("census_search.cli.Census1901_1911Searcher", return_value=mock_old),
        ):
            result = runner.invoke(app, ["link", "Corrigan", "--birth-year", "1880"])
        assert result.exit_code == 0
        assert mock_old.search_both_years.call_count >= 1


# ---------------------------------------------------------------------------
# Filtering logic (first-name, age tolerance, prefer aged records)
# ---------------------------------------------------------------------------

class TestLinkFiltering:
    """Tests for the client-side filtering applied to raw 1926 search results."""

    def _invoke(self, raw_records, args):
        mock_1926, mock_old = _setup_link_mocks(raw_records)
        with (
            patch("census_search.cli.Census1926Searcher", return_value=mock_1926),
            patch("census_search.cli.Census1901_1911Searcher", return_value=mock_old),
        ):
            return runner.invoke(app, args)

    def test_first_name_mismatch_is_excluded(self):
        """A record whose first name doesn't match --first-name is filtered out."""
        wrong_name = CensusRecord(
            census_year=1926, surname="Gilligan", first_name="Patrick", age=44,
            county="Kilkenny", townland_street="Lamogue", ded="Kilmaganny",
        )
        result = self._invoke(
            [wrong_name],
            ["link", "Gilligan", "--first-name", "Fred", "--birth-year", "1882"],
        )
        assert result.exit_code == 0
        assert " 44 " not in result.output  # age from excluded record should not appear

    def test_first_name_match_is_case_insensitive(self):
        """First-name filter is case-insensitive."""
        rec = CensusRecord(
            census_year=1926, surname="Gilligan", first_name="fred", age=44,
            county="Kilkenny", townland_street="Lamogue", ded="Kilmaganny",
        )
        result = self._invoke(
            [rec],
            ["link", "Gilligan", "--first-name", "Fred", "--birth-year", "1882"],
        )
        assert " 44 " in result.output  # record was kept despite lowercase name

    def test_age_outside_tolerance_excluded(self):
        """A record whose age is outside birth_year ± age_tolerance is filtered out."""
        # birth_year=1882 → expected age in 1926 = 44; tolerance default = 3
        # age 48 is 4 years off → outside tolerance
        too_old = CensusRecord(
            census_year=1926, surname="Corrigan", first_name="James", age=48,
            county="Kilkenny", townland_street="Lamogue", ded="Kilmaganny",
        )
        result = self._invoke(
            [too_old],
            ["link", "Corrigan", "--first-name", "James", "--birth-year", "1882"],
        )
        assert " 48 " not in result.output

    def test_age_within_tolerance_included(self):
        """A record whose age is within the tolerance window is kept."""
        # age 47 is 3 years off → exactly on the boundary
        boundary = CensusRecord(
            census_year=1926, surname="Corrigan", first_name="James", age=47,
            county="Kilkenny", townland_street="Lamogue", ded="Kilmaganny",
        )
        result = self._invoke(
            [boundary],
            ["link", "Corrigan", "--first-name", "James", "--birth-year", "1882"],
        )
        assert " 47 " in result.output

    def test_custom_age_tolerance_respected(self):
        """--age-tolerance overrides the default 3-year window."""
        # age 48 is 4 years off — excluded at default tolerance but included at tolerance=5
        rec = CensusRecord(
            census_year=1926, surname="Corrigan", first_name="James", age=48,
            county="Kilkenny", townland_street="Lamogue", ded="Kilmaganny",
        )
        result = self._invoke(
            [rec],
            ["link", "Corrigan", "--first-name", "James", "--birth-year", "1882", "--age-tolerance", "5"],
        )
        assert " 48 " in result.output

    def test_age_before_widens_older_end(self):
        """--age-before allows matching records older than default tolerance."""
        # birth_year=1917, age_1926=9, default tol=3 → window [6,12]
        # age 4 is 5 years older → excluded at default but included at --age-before 5
        older = CensusRecord(census_year=1926, surname="Corrigan", first_name="Joseph",
                             age=4, sex="Male", county="Kilkenny",
                             townland_street="Lamogue", ded="Kilmaganny")
        result = self._invoke(
            [older],
            ["link", "Corrigan", "--first-name", "Joseph", "--birth-year", "1917",
             "--age-before", "5"],
        )
        assert " 4 " in result.output  # included because tol_before=5

    def test_age_before_default_excludes_older(self):
        """Without --age-before, age 4 for birth_year=1917 is excluded (5 years off)."""
        older = CensusRecord(census_year=1926, surname="Corrigan", first_name="Joseph",
                             age=4, sex="Male", county="Kilkenny",
                             townland_street="Lamogue", ded="Kilmaganny")
        result = self._invoke(
            [older],
            ["link", "Corrigan", "--first-name", "Joseph", "--birth-year", "1917"],
        )
        assert " 4 " not in result.output  # excluded at default ±3

    def test_age_after_widens_younger_end(self):
        """--age-after allows matching records younger than default tolerance."""
        # birth_year=1917, age_1926=9, default tol=3 → window [6,12]
        # age 14 is 5 years younger → excluded at default but included at --age-after 10
        younger = CensusRecord(census_year=1926, surname="Corrigan", first_name="Joseph",
                               age=14, sex="Male", county="Kilkenny",
                               townland_street="Lamogue", ded="Kilmaganny")
        result = self._invoke(
            [younger],
            ["link", "Corrigan", "--first-name", "Joseph", "--birth-year", "1917",
             "--age-after", "10"],
        )
        assert " 14 " in result.output

    def test_asymmetric_window_label_shown(self):
        """When --age-before differs from --age-after, label shows -N/+M format."""
        rec = CensusRecord(census_year=1926, surname="Corrigan", first_name="Joseph",
                           age=9, sex="Male", county="Kilkenny",
                           townland_street="Lamogue", ded="Kilmaganny")
        result = self._invoke(
            [rec],
            ["link", "Corrigan", "--first-name", "Joseph", "--birth-year", "1917",
             "--age-before", "5", "--age-after", "10"],
        )
        assert "-5/+10" in result.output

    def test_symmetric_window_label_shown(self):
        """When age-tolerance is symmetric, label shows ±N format."""
        rec = CensusRecord(census_year=1926, surname="Corrigan", first_name="James",
                           age=44, sex="Male", county="Kilkenny",
                           townland_street="Lamogue", ded="Kilmaganny")
        result = self._invoke(
            [rec],
            ["link", "Corrigan", "--first-name", "James", "--birth-year", "1882"],
        )
        assert "±3" in result.output

    def test_ageless_record_used_only_when_no_aged_records(self):
        """A record without an age is kept only when no aged records pass the filter."""
        aged = CensusRecord(
            census_year=1926, surname="Corrigan", first_name="James", age=44,
            county="Kilkenny", townland_street="Lamogue", ded="Kilmaganny",
        )
        ageless = CensusRecord(
            census_year=1926, surname="Corrigan", first_name="James", age=None,
            county="Kilkenny", townland_street="Lamogue", ded="Kilmaganny",
        )
        mock_1926, mock_old = _setup_link_mocks([aged, ageless])
        # The ageless record should be dropped in favour of the aged one
        # → only 1 match → household fetch is triggered (search called twice)
        with (
            patch("census_search.cli.Census1926Searcher", return_value=mock_1926),
            patch("census_search.cli.Census1901_1911Searcher", return_value=mock_old),
        ):
            runner.invoke(app, ["link", "Corrigan", "--first-name", "James", "--birth-year", "1882"])
        assert mock_1926.search.call_count == 2  # household fetch triggered → single match used

    def test_ageless_record_accepted_when_no_aged_alternative(self):
        """A record without an age is accepted when it is the only match."""
        ageless = CensusRecord(
            census_year=1926, surname="Corrigan", first_name="James", age=None,
            county="Kilkenny", townland_street="Lamogue", ded="Kilmaganny",
        )
        mock_1926, mock_old = _setup_link_mocks([ageless])
        with (
            patch("census_search.cli.Census1926Searcher", return_value=mock_1926),
            patch("census_search.cli.Census1901_1911Searcher", return_value=mock_old),
        ):
            result = runner.invoke(app, ["link", "Corrigan", "--first-name", "James", "--birth-year", "1882"])
        assert "James Corrigan" in result.output  # record shown even without age

    def test_no_1926_match_does_not_suppress_1911_results(self):
        """Even when 1926 has no match, matching 1911 records are still displayed."""
        mock_1926, mock_old = _setup_link_mocks(
            [],
            records_1911=[CensusRecord(census_year=1911, surname="Gilligan", first_name="Fred", age=29)],
        )
        with (
            patch("census_search.cli.Census1926Searcher", return_value=mock_1926),
            patch("census_search.cli.Census1901_1911Searcher", return_value=mock_old),
        ):
            result = runner.invoke(app, ["link", "Gilligan", "--first-name", "Fred", "--birth-year", "1882"])
        assert result.exit_code == 0
        assert "1911" in result.output


# ---------------------------------------------------------------------------
# browse command
# ---------------------------------------------------------------------------

class TestBrowseCommand:
    def test_exits_0_with_results(self):
        mock_1926 = AsyncMock()
        mock_1926.__aenter__ = AsyncMock(return_value=mock_1926)
        mock_1926.__aexit__ = AsyncMock(return_value=False)
        mock_1926.search = AsyncMock(return_value=_make_result(1926, [_corrigan_1926()]))
        with patch("census_search.cli.Census1926Searcher", return_value=mock_1926):
            result = runner.invoke(app, ["browse", "--county", "Kilkenny"])
        assert result.exit_code == 0

    def test_exits_1_on_no_results(self):
        mock_1926 = AsyncMock()
        mock_1926.__aenter__ = AsyncMock(return_value=mock_1926)
        mock_1926.__aexit__ = AsyncMock(return_value=False)
        mock_1926.search = AsyncMock(return_value=_make_result(1926, []))
        with patch("census_search.cli.Census1926Searcher", return_value=mock_1926):
            result = runner.invoke(app, ["browse", "--county", "Kilkenny"])
        assert result.exit_code == 1


# ---------------------------------------------------------------------------
# 1901 / 1911 commands
# ---------------------------------------------------------------------------

def _corrigan_1911() -> CensusRecord:
    return CensusRecord(
        census_year=1911, surname="Corrigan", first_name="James",
        age=29, sex="Male", county="Kilkenny",
        townland_street="Lamogue", ded="Kilmaganny",
    )


def _corrigan_1901() -> CensusRecord:
    return CensusRecord(
        census_year=1901, surname="Corrigan", first_name="James",
        age=19, sex="Male", county="Kilkenny",
        townland_street="Lamogue", ded="Kilmaganny",
    )


def _setup_old_mock(records_1911=None, records_1901=None):
    mock_old = AsyncMock()
    mock_old.__aenter__ = AsyncMock(return_value=mock_old)
    mock_old.__aexit__ = AsyncMock(return_value=False)

    async def _search_side_effect(**kwargs):
        yr = kwargs.get("census_year")
        if yr == 1911:
            return _make_result(1911, records_1911 or [])
        return _make_result(1901, records_1901 or [])

    mock_old.search = AsyncMock(side_effect=_search_side_effect)
    return mock_old


class TestCensus1911Command:
    def test_exits_0_with_results(self):
        mock_old = _setup_old_mock(records_1911=[_corrigan_1911()])
        with patch("census_search.cli.Census1901_1911Searcher", return_value=mock_old):
            result = runner.invoke(app, ["1911", "Corrigan", "--county", "Kilkenny"])
        assert result.exit_code == 0

    def test_shows_surname_in_output(self):
        mock_old = _setup_old_mock(records_1911=[_corrigan_1911()])
        with patch("census_search.cli.Census1901_1911Searcher", return_value=mock_old):
            result = runner.invoke(app, ["1911", "Corrigan", "--county", "Kilkenny"])
        assert "Corrigan" in result.output

    def test_only_searches_1911(self):
        mock_old = _setup_old_mock(records_1911=[_corrigan_1911()])
        with patch("census_search.cli.Census1901_1911Searcher", return_value=mock_old):
            runner.invoke(app, ["1911", "Corrigan", "--county", "Kilkenny"])
        calls = [c.kwargs.get("census_year") for c in mock_old.search.call_args_list]
        assert all(yr == 1911 for yr in calls)

    def test_sex_filter_applied_client_side(self):
        male = CensusRecord(census_year=1911, surname="Corrigan", first_name="James",
                            age=29, sex="Male", county="Kilkenny")
        female = CensusRecord(census_year=1911, surname="Corrigan", first_name="Mary",
                              age=27, sex="Female", county="Kilkenny")
        mock_old = _setup_old_mock(records_1911=[male, female])
        with patch("census_search.cli.Census1901_1911Searcher", return_value=mock_old):
            result = runner.invoke(app, ["1911", "Corrigan", "--sex", "Male"])
        assert "James" in result.output
        assert "Mary" not in result.output

    def test_no_results_exits_0_with_message(self):
        mock_old = _setup_old_mock()
        with patch("census_search.cli.Census1901_1911Searcher", return_value=mock_old):
            result = runner.invoke(app, ["1911", "Corrigan"])
        assert result.exit_code == 0
        assert "No results" in result.output

    def test_max_respected(self):
        mock_old = _setup_old_mock(records_1911=[_corrigan_1911()])
        with patch("census_search.cli.Census1901_1911Searcher", return_value=mock_old):
            runner.invoke(app, ["1911", "Corrigan", "--max", "300"])
        assert mock_old.search.call_args.kwargs.get("max_results") == 300


class TestCensus1901Command:
    def test_exits_0_with_results(self):
        mock_old = _setup_old_mock(records_1901=[_corrigan_1901()])
        with patch("census_search.cli.Census1901_1911Searcher", return_value=mock_old):
            result = runner.invoke(app, ["1901", "Corrigan", "--county", "Kilkenny"])
        assert result.exit_code == 0

    def test_only_searches_1901(self):
        mock_old = _setup_old_mock(records_1901=[_corrigan_1901()])
        with patch("census_search.cli.Census1901_1911Searcher", return_value=mock_old):
            runner.invoke(app, ["1901", "Corrigan", "--county", "Kilkenny"])
        calls = [c.kwargs.get("census_year") for c in mock_old.search.call_args_list]
        assert all(yr == 1901 for yr in calls)

    def test_commands_appear_in_help(self):
        result = runner.invoke(app, ["--help"])
        assert "1901" in result.output
        assert "1911" in result.output


# ---------------------------------------------------------------------------
# 1821 / 1831 / 1841 / 1851 commands
# ---------------------------------------------------------------------------

def _setup_fragment_mock(records: list[CensusRecord], census_year: int):
    mock = AsyncMock()
    mock.__aenter__ = AsyncMock(return_value=mock)
    mock.__aexit__ = AsyncMock(return_value=False)
    mock.search = AsyncMock(return_value=_make_result(census_year, records))
    return mock


def _murphy_1851() -> CensusRecord:
    return CensusRecord(
        census_year=1851, surname="Murphy", first_name="Eliza",
        age=43, sex="Female", county="Antrim",
        townland_street="Montiaghs", ded="Aghagallon",
        birthplace="Antrim",
    )


def _corrigan_1831() -> CensusRecord:
    return CensusRecord(
        census_year=1831, surname="Corrigan", first_name="Robt",
        county="", townland_street="Bishop Street", ded="Templemore",
    )


def _murphy_1821() -> CensusRecord:
    return CensusRecord(
        census_year=1821, surname="Murphy", first_name="Bernard",
        age=39, county="Meath", townland_street="Manorland", ded="Trim",
        relationship="Head",
    )


class TestCensus1851Command:
    def test_exits_0_with_results(self):
        mock = _setup_fragment_mock([_murphy_1851()], 1851)
        with patch("census_search.cli.Census1821_1851Searcher", return_value=mock):
            result = runner.invoke(app, ["1851", "Murphy", "--county", "Antrim"])
        assert result.exit_code == 0

    def test_shows_surname_in_output(self):
        mock = _setup_fragment_mock([_murphy_1851()], 1851)
        with patch("census_search.cli.Census1821_1851Searcher", return_value=mock):
            result = runner.invoke(app, ["1851", "Murphy"])
        assert "Murphy" in result.output

    def test_passes_correct_year_to_searcher(self):
        mock = _setup_fragment_mock([_murphy_1851()], 1851)
        with patch("census_search.cli.Census1821_1851Searcher", return_value=mock):
            runner.invoke(app, ["1851", "Murphy"])
        assert mock.search.call_args.kwargs["census_year"] == 1851

    def test_sex_filter_applied_client_side(self):
        male = CensusRecord(census_year=1851, surname="Murphy", first_name="Robert",
                            age=8, sex="Male", county="Antrim")
        female = CensusRecord(census_year=1851, surname="Murphy", first_name="Eliza",
                              age=43, sex="Female", county="Antrim")
        mock = _setup_fragment_mock([male, female], 1851)
        with patch("census_search.cli.Census1821_1851Searcher", return_value=mock):
            result = runner.invoke(app, ["1851", "Murphy", "--sex", "Male"])
        assert "Robert" in result.output
        assert "Eliza" not in result.output

    def test_no_results_exits_0_with_message(self):
        mock = _setup_fragment_mock([], 1851)
        with patch("census_search.cli.Census1821_1851Searcher", return_value=mock):
            result = runner.invoke(app, ["1851", "Murphy"])
        assert result.exit_code == 0
        assert "No results" in result.output

    def test_max_passed_to_searcher(self):
        mock = _setup_fragment_mock([_murphy_1851()], 1851)
        with patch("census_search.cli.Census1821_1851Searcher", return_value=mock):
            runner.invoke(app, ["1851", "Murphy", "--max", "50"])
        assert mock.search.call_args.kwargs["max_results"] == 50

    def test_county_passed_to_searcher(self):
        mock = _setup_fragment_mock([_murphy_1851()], 1851)
        with patch("census_search.cli.Census1821_1851Searcher", return_value=mock):
            runner.invoke(app, ["1851", "Murphy", "--county", "Antrim"])
        assert mock.search.call_args.kwargs["county"] == "Antrim"

    def test_shows_age_in_output(self):
        mock = _setup_fragment_mock([_murphy_1851()], 1851)
        with patch("census_search.cli.Census1821_1851Searcher", return_value=mock):
            result = runner.invoke(app, ["1851", "Murphy"])
        assert " 43 " in result.output


class TestCensus1841Command:
    def test_exits_0_with_results(self):
        rec = CensusRecord(census_year=1841, surname="Corrigan", first_name="Catherine",
                           age=70, sex="Female", county="Kilkenny")
        mock = _setup_fragment_mock([rec], 1841)
        with patch("census_search.cli.Census1821_1851Searcher", return_value=mock):
            result = runner.invoke(app, ["1841", "Corrigan"])
        assert result.exit_code == 0

    def test_passes_correct_year_to_searcher(self):
        rec = CensusRecord(census_year=1841, surname="Corrigan", age=70)
        mock = _setup_fragment_mock([rec], 1841)
        with patch("census_search.cli.Census1821_1851Searcher", return_value=mock):
            runner.invoke(app, ["1841", "Corrigan"])
        assert mock.search.call_args.kwargs["census_year"] == 1841

    def test_sex_filter_applied_client_side(self):
        male = CensusRecord(census_year=1841, surname="Murphy", first_name="John",
                            age=30, sex="Male", county="Cork")
        female = CensusRecord(census_year=1841, surname="Murphy", first_name="Brigid",
                              age=28, sex="Female", county="Cork")
        mock = _setup_fragment_mock([male, female], 1841)
        with patch("census_search.cli.Census1821_1851Searcher", return_value=mock):
            result = runner.invoke(app, ["1841", "Murphy", "--sex", "Female"])
        assert "Brigid" in result.output
        assert "John" not in result.output


class TestCensus1831Command:
    def test_exits_0_with_results(self):
        mock = _setup_fragment_mock([_corrigan_1831()], 1831)
        with patch("census_search.cli.Census1821_1851Searcher", return_value=mock):
            result = runner.invoke(app, ["1831", "Corrigan"])
        assert result.exit_code == 0

    def test_passes_correct_year_to_searcher(self):
        mock = _setup_fragment_mock([_corrigan_1831()], 1831)
        with patch("census_search.cli.Census1821_1851Searcher", return_value=mock):
            runner.invoke(app, ["1831", "Corrigan"])
        assert mock.search.call_args.kwargs["census_year"] == 1831

    def test_shows_townland_in_output(self):
        mock = _setup_fragment_mock([_corrigan_1831()], 1831)
        with patch("census_search.cli.Census1821_1851Searcher", return_value=mock):
            result = runner.invoke(app, ["1831", "Corrigan"])
        assert "Bishop" in result.output

    def test_no_sex_option(self):
        """1831 command has no --sex flag (no individual sex data in that census)."""
        mock = _setup_fragment_mock([_corrigan_1831()], 1831)
        with patch("census_search.cli.Census1821_1851Searcher", return_value=mock):
            result = runner.invoke(app, ["1831", "Corrigan", "--sex", "Male"])
        assert result.exit_code != 0  # unknown option


class TestCensus1821Command:
    def test_exits_0_with_results(self):
        mock = _setup_fragment_mock([_murphy_1821()], 1821)
        with patch("census_search.cli.Census1821_1851Searcher", return_value=mock):
            result = runner.invoke(app, ["1821", "Murphy", "--county", "Meath"])
        assert result.exit_code == 0

    def test_passes_correct_year_to_searcher(self):
        mock = _setup_fragment_mock([_murphy_1821()], 1821)
        with patch("census_search.cli.Census1821_1851Searcher", return_value=mock):
            runner.invoke(app, ["1821", "Murphy"])
        assert mock.search.call_args.kwargs["census_year"] == 1821

    def test_shows_age_in_output(self):
        mock = _setup_fragment_mock([_murphy_1821()], 1821)
        with patch("census_search.cli.Census1821_1851Searcher", return_value=mock):
            result = runner.invoke(app, ["1821", "Murphy"])
        assert " 39 " in result.output

    def test_no_sex_option(self):
        """1821 command has no --sex flag (no sex column in 1821 census)."""
        mock = _setup_fragment_mock([_murphy_1821()], 1821)
        with patch("census_search.cli.Census1821_1851Searcher", return_value=mock):
            result = runner.invoke(app, ["1821", "Murphy", "--sex", "Male"])
        assert result.exit_code != 0  # unknown option

    def test_no_results_exits_0_with_message(self):
        mock = _setup_fragment_mock([], 1821)
        with patch("census_search.cli.Census1821_1851Searcher", return_value=mock):
            result = runner.invoke(app, ["1821", "Murphy"])
        assert result.exit_code == 0
        assert "No results" in result.output


# ---------------------------------------------------------------------------
# Military search (--service-number)
# ---------------------------------------------------------------------------

def _setup_war_office_mock(records: list[MilitaryRecord] | None = None):
    mock_wo = AsyncMock()
    mock_wo.__aenter__ = AsyncMock(return_value=mock_wo)
    mock_wo.__aexit__ = AsyncMock(return_value=False)
    mock_wo.search = AsyncMock(return_value=records or [])
    return mock_wo


class TestMilitarySearch:
    """Tests for --service-number military search integration in link command."""

    def test_service_number_triggers_war_office_search(self):
        mock_1926, mock_old = _setup_link_mocks([_corrigan_1926()])
        mock_wo = _setup_war_office_mock()
        with (
            patch("census_search.cli.Census1926Searcher", return_value=mock_1926),
            patch("census_search.cli.Census1901_1911Searcher", return_value=mock_old),
            patch("census_search.cli.WarOfficeSearcher", return_value=mock_wo),
        ):
            result = runner.invoke(app, ["link", "Hennessy", "--first-name", "Patrick",
                                         "--birth-year", "1888", "--service-number", "3989"])
        assert result.exit_code == 0
        mock_wo.search.assert_called_once()

    def test_military_table_shown_when_records_found(self):
        mock_1926, mock_old = _setup_link_mocks([_corrigan_1926()])
        military_record = MilitaryRecord(
            series="WO 372",
            record_type="Medal card",
            reference="WO 372/9/144384",
            regiment="Royal Irish Regiment",
            service_number="3989",
            rank="Private",
            dates="1914-1920",
        )
        mock_wo = _setup_war_office_mock([military_record])
        with (
            patch("census_search.cli.Census1926Searcher", return_value=mock_1926),
            patch("census_search.cli.Census1901_1911Searcher", return_value=mock_old),
            patch("census_search.cli.WarOfficeSearcher", return_value=mock_wo),
        ):
            result = runner.invoke(app, ["link", "Hennessy", "--first-name", "Patrick",
                                         "--birth-year", "1888", "--service-number", "3989"])
        assert result.exit_code == 0
        assert "Military Records" in result.output
        assert "3989" in result.output

    def test_pension_table_shown_when_pin26_found(self):
        mock_1926, mock_old = _setup_link_mocks([_corrigan_1926()])
        pension_record = MilitaryRecord(
            series="PIN 26",
            record_type="Pension file",
            reference="PIN 26/18129",
            regiment="Royal Irish Regiment",
            dates="1915-1947",
        )
        mock_wo = _setup_war_office_mock([pension_record])
        with (
            patch("census_search.cli.Census1926Searcher", return_value=mock_1926),
            patch("census_search.cli.Census1901_1911Searcher", return_value=mock_old),
            patch("census_search.cli.WarOfficeSearcher", return_value=mock_wo),
        ):
            result = runner.invoke(app, ["link", "Hennessy", "--first-name", "Patrick",
                                         "--birth-year", "1888", "--service-number", "3989"])
        assert result.exit_code == 0
        assert "Dependants & Pensions" in result.output
        assert "PIN 26" in result.output

    def test_no_service_number_skips_war_office_search(self):
        mock_1926, mock_old = _setup_link_mocks([_corrigan_1926()])
        mock_wo = _setup_war_office_mock()
        with (
            patch("census_search.cli.Census1926Searcher", return_value=mock_1926),
            patch("census_search.cli.Census1901_1911Searcher", return_value=mock_old),
            patch("census_search.cli.WarOfficeSearcher", return_value=mock_wo) as wo_cls,
        ):
            runner.invoke(app, ["link", "Corrigan", "--birth-year", "1880"])
        wo_cls.assert_not_called()

    def test_service_number_with_single_match_fetches_household(self):
        mock_1926, mock_old = _setup_link_mocks([_corrigan_1926()])
        mock_wo = _setup_war_office_mock()
        with (
            patch("census_search.cli.Census1926Searcher", return_value=mock_1926),
            patch("census_search.cli.Census1901_1911Searcher", return_value=mock_old),
            patch("census_search.cli.WarOfficeSearcher", return_value=mock_wo),
        ):
            runner.invoke(app, ["link", "Corrigan", "--birth-year", "1880",
                                 "--service-number", "3989"])
        assert mock_1926.search.call_count == 2


class TestFragmentCommandsInHelp:
    def test_all_fragment_years_in_help(self):
        result = runner.invoke(app, ["--help"])
        out = result.output
        assert "1851" in out
        assert "1841" in out
        assert "1831" in out
        assert "1821" in out

    def test_1851_help(self):
        result = runner.invoke(app, ["1851", "--help"])
        assert result.exit_code == 0
        assert "--county" in _plain(result.output)
        assert "--sex" in _plain(result.output)

    def test_1831_help_no_sex_flag(self):
        result = runner.invoke(app, ["1831", "--help"])
        assert result.exit_code == 0
        assert "--sex" not in _plain(result.output)
