"""Tests for the CLI layer (no browser, mocked searchers)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from typer.testing import CliRunner

from census_search.cli import app
from census_search.models import CensusRecord, SearchResult

runner = CliRunner()


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
        assert "--birth-year" in result.output
        assert "--first-name" in result.output
        assert "--county" in result.output
        assert "--sex" in result.output
        assert "--expand" in result.output

    def test_browse_help(self):
        result = runner.invoke(app, ["browse", "--help"])
        assert result.exit_code == 0
        assert "--county" in result.output


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

    def test_birth_year_required(self):
        result = runner.invoke(app, ["link", "Corrigan"])
        assert result.exit_code != 0

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
        """Multiple 1926 matches do not trigger household fetch."""
        mock_1926, mock_old = _setup_link_mocks([_corrigan_1926(), _corrigan_1926()])
        with (
            patch("census_search.cli.Census1926Searcher", return_value=mock_1926),
            patch("census_search.cli.Census1901_1911Searcher", return_value=mock_old),
        ):
            runner.invoke(app, ["link", "Corrigan", "--birth-year", "1880"])
        assert mock_1926.search.call_count == 1

    def test_no_1926_match_shows_no_match(self):
        """When no 1926 records pass the filter, 1926 shows 'no match', not a synthetic record."""
        mock_1926, mock_old = _setup_link_mocks([])
        with (
            patch("census_search.cli.Census1926Searcher", return_value=mock_1926),
            patch("census_search.cli.Census1901_1911Searcher", return_value=mock_old),
        ):
            result = runner.invoke(app, ["link", "Gilligan", "--first-name", "Fred", "--birth-year", "1882"])
        assert result.exit_code == 0
        assert "1926" in result.output
        assert "no match" in result.output
        assert "age 44" not in result.output

    def test_expand_links_household_members(self):
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
            result = runner.invoke(app, ["link", "Corrigan", "--birth-year", "1880", "--expand"])
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
        assert "no match" in result.output
        assert "age 44" not in result.output

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
        assert "age 44" in result.output  # record was kept despite lowercase name

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
        assert "age 48" not in result.output

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
        assert "age 47" in result.output

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
        assert "age 48" in result.output

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
