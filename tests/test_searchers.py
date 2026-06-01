"""Tests for census searcher parsing logic (no browser required)."""

from census_search.searchers.census_1821_1851 import BASE_URL, _parse_row, _TableParser
from census_search.searchers.census_1821_1851 import _build_params as _build_params_1821
from census_search.searchers.census_1901_1911 import (
    _build_params,
    _parse_record,
)
from census_search.searchers.census_1926 import (
    SEARCH_BASE,
    Census1926Searcher,
    _build_search_url,
    _parse_record_from_row,
    _safe_int,
)
from census_search.searchers.war_office import _normalise_regiment

# ---------------------------------------------------------------------------
# URL builders
# ---------------------------------------------------------------------------

class TestBuildSearchUrl1926:
    def test_no_params(self):
        url = _build_search_url()
        assert url == SEARCH_BASE

    def test_surname_only(self):
        url = _build_search_url(surname="Murphy")
        assert "surname=Murphy" in url
        assert url.startswith(SEARCH_BASE)

    def test_all_params(self):
        url = _build_search_url(
            surname="Corrigan",
            first_name="James",
            county="Kilkenny",
            townland="High Street",
            ded="Kilkenny Urban",
            exact=True,
        )
        assert "surname=Corrigan" in url
        assert "firstname=James" in url
        assert "county=Kilkenny" in url
        assert "townland=High+Street" in url or "townland=High%20Street" in url
        assert "ded=Kilkenny+Urban" in url or "ded=Kilkenny%20Urban" in url
        assert "exact=true" in url

    def test_exact_false_not_in_url(self):
        url = _build_search_url(surname="Murphy", exact=False)
        assert "exact" not in url

    def test_empty_strings_excluded(self):
        url = _build_search_url(surname="Murphy", first_name="", county="")
        assert "firstname" not in url
        assert "county" not in url


class TestBuildParams1901_1911:
    def test_no_params(self):
        params = _build_params()
        assert "limit" in params

    def test_with_year(self):
        params = _build_params(surname="Murphy", census_year=1911)
        assert params["census_year"] == 1911
        assert params["surname__icontains"] == "Murphy"

    def test_with_age_range(self):
        params = _build_params(surname="Murphy", age_from=28, age_to=34)
        assert params["age__gte"] == 28
        assert params["age__lte"] == 34

    def test_exact_uses_iexact(self):
        params = _build_params(surname="Murphy", exact=True)
        assert "surname__iexact" in params
        assert "surname__icontains" not in params


# ---------------------------------------------------------------------------
# Record parsing — 1926
# ---------------------------------------------------------------------------

class TestParseRecordFromRow1926:
    def test_lowercase_keys(self):
        row = {"surname": "Murphy", "firstname": "John", "age": "40", "sex": "Male",
               "county": "Dublin", "townland": "Grafton Street", "ded": "Dublin South"}
        r = _parse_record_from_row(row)
        assert r.surname == "Murphy"
        assert r.first_name == "John"
        assert r.age == 40
        assert r.sex == "Male"
        assert r.county == "Dublin"
        assert r.townland_street == "Grafton Street"
        assert r.ded == "Dublin South"
        assert r.census_year == 1926

    def test_capitalized_keys(self):
        row = {"Surname": "Corrigan", "FirstName": "James", "Age": "46",
               "Sex": "Male", "County": "Kilkenny", "DED": "Kilkenny Urban"}
        r = _parse_record_from_row(row)
        assert r.surname == "Corrigan"
        assert r.first_name == "James"
        assert r.age == 46
        assert r.ded == "Kilkenny Urban"

    def test_first_name_fallback_key(self):
        row = {"surname": "Murphy", "first_name": "Patrick"}
        r = _parse_record_from_row(row)
        assert r.first_name == "Patrick"

    def test_townland_fallback_key(self):
        row = {"surname": "Murphy", "townland_street": "Main St"}
        r = _parse_record_from_row(row)
        assert r.townland_street == "Main St"

    def test_detail_url(self):
        row = {"surname": "Murphy", "url": "https://example.com/record/42"}
        r = _parse_record_from_row(row)
        assert r.detail_url == "https://example.com/record/42"

    def test_detail_url_fallback_key(self):
        row = {"surname": "Murphy", "detail_url": "https://example.com/record/42"}
        r = _parse_record_from_row(row)
        assert r.detail_url == "https://example.com/record/42"

    def test_invalid_age_is_none(self):
        row = {"surname": "Murphy", "age": "unknown"}
        r = _parse_record_from_row(row)
        assert r.age is None

    def test_null_age_is_none(self):
        row = {"surname": "Murphy", "age": None}
        r = _parse_record_from_row(row)
        assert r.age is None

    def test_empty_row(self):
        r = _parse_record_from_row({})
        assert r.surname == ""
        assert r.first_name == ""
        assert r.age is None
        assert r.census_year == 1926

    def test_all_optional_fields(self):
        row = {
            "surname": "Murphy",
            "relationship": "Head",
            "religion": "Roman Catholic",
            "occupation": "Farmer",
            "marital_status": "Married",
            "birthplace": "Cork",
            "irish_language": "Irish and English",
        }
        r = _parse_record_from_row(row)
        assert r.relationship == "Head"
        assert r.religion == "Roman Catholic"
        assert r.occupation == "Farmer"
        assert r.marital_status == "Married"
        assert r.birthplace == "Cork"
        assert r.irish_language == "Irish and English"

    def test_capitalized_optional_fields(self):
        row = {
            "Surname": "Murphy",
            "RelationshipToHead": "Son",
            "Religion": "Protestant",
            "PersonalOccupation": "Scholar",
            "MaritalStatus": "Single",
            "BirthplaceCounty": "Mayo",
            "IrishLanguage": "English only",
        }
        r = _parse_record_from_row(row)
        assert r.relationship == "Son"
        assert r.religion == "Protestant"
        assert r.occupation == "Scholar"
        assert r.marital_status == "Single"
        assert r.birthplace == "Mayo"
        assert r.irish_language == "English only"


# ---------------------------------------------------------------------------
# Record parsing — 1901/1911
# ---------------------------------------------------------------------------

class TestParseRecord1901_1911:
    def test_basic(self):
        row = {"surname": "Corrigan", "firstname": "James", "age": "31"}
        r = _parse_record(row, 1911)
        assert r.census_year == 1911
        assert r.surname == "Corrigan"
        assert r.age == 31

    def test_year_from_row(self):
        row = {"surname": "Murphy", "census_year": 1901, "age": 21}
        r = _parse_record(row, 0)
        assert r.census_year == 1901


# ---------------------------------------------------------------------------
# _parse_api_response — 1926 searcher
# ---------------------------------------------------------------------------

class TestParseApiResponse1926:
    def setup_method(self):
        self.searcher = Census1926Searcher.__new__(Census1926Searcher)

    def test_results_list_pattern(self):
        data = {
            "total": 2,
            "results": [
                {"surname": "Murphy", "firstname": "John", "age": "40"},
                {"surname": "Murphy", "firstname": "Mary", "age": "35"},
            ],
        }
        records, total, _ = self.searcher._parse_api_response(data)
        assert total == 2
        assert len(records) == 2
        assert records[0].first_name == "John"
        assert records[1].first_name == "Mary"

    def test_data_key_pattern(self):
        data = {"count": 1, "data": [{"surname": "Brien", "age": "50"}]}
        records, total, _ = self.searcher._parse_api_response(data)
        assert total == 1
        assert records[0].surname == "Brien"

    def test_records_key_pattern(self):
        data = {"total": 1, "records": [{"surname": "Kelly", "age": "28"}]}
        records, total, _ = self.searcher._parse_api_response(data)
        assert records[0].surname == "Kelly"

    def test_elasticsearch_pattern(self):
        data = {
            "hits": {
                "total": {"value": 1},
                "hits": [
                    {"_source": {"surname": "Walsh", "firstname": "Brigid", "age": "22"}}
                ],
            }
        }
        records, total, _ = self.searcher._parse_api_response(data)
        assert total == 1
        assert records[0].surname == "Walsh"
        assert records[0].first_name == "Brigid"
        assert records[0].age == 22

    def test_plain_list_pattern(self):
        data = [
            {"surname": "Ryan", "age": "55"},
            {"surname": "Byrne", "age": "33"},
        ]
        records, total, _ = self.searcher._parse_api_response(data)
        assert total == 2
        assert records[0].surname == "Ryan"
        assert records[1].surname == "Byrne"

    def test_empty_results(self):
        data = {"total": 0, "results": []}
        records, total, _ = self.searcher._parse_api_response(data)
        assert total == 0
        assert records == []

    def test_total_falls_back_to_len(self):
        data = {"results": [{"surname": "Murphy"}, {"surname": "Brien"}]}
        records, total, _ = self.searcher._parse_api_response(data)
        assert total == 2

    def test_non_source_item_in_hits(self):
        """Items without _source should be parsed directly."""
        data = {
            "hits": {
                "total": {"value": 1},
                "hits": [{"surname": "Nolan", "age": "44"}],
            }
        }
        records, total, _ = self.searcher._parse_api_response(data)
        assert records[0].surname == "Nolan"


# ---------------------------------------------------------------------------
# _safe_int
# ---------------------------------------------------------------------------

class TestSafeInt:
    def test_valid_int(self):
        assert _safe_int("42") == 42

    def test_int_with_whitespace(self):
        assert _safe_int("  7  ") == 7

    def test_zero(self):
        assert _safe_int("0") == 0

    def test_non_numeric(self):
        assert _safe_int("unknown") is None

    def test_empty_string(self):
        assert _safe_int("") is None

    def test_float_string(self):
        assert _safe_int("3.5") is None

    def test_none_input(self):
        assert _safe_int(None) is None


# ---------------------------------------------------------------------------
# 1821–1851 searcher
# ---------------------------------------------------------------------------

class TestBuildParams1821_1851:
    def test_basic_1851(self):
        params = _build_params_1821(census_year=1851, surname="Murphy")
        assert params["census_year"] == 1851
        assert params["surname"] == "Murphy"
        assert params["county1851"] == ""
        assert "county1821" not in params
        assert "county1901" not in params

    def test_county_uses_year_specific_key(self):
        for year in (1821, 1831, 1841, 1851):
            params = _build_params_1821(census_year=year, county="Kilkenny")
            assert params[f"county{year}"] == "Kilkenny"

    def test_offset_included_when_nonzero(self):
        params = _build_params_1821(census_year=1851, offset=100)
        assert params["pager.offset"] == 100

    def test_offset_omitted_when_zero(self):
        params = _build_params_1821(census_year=1851, offset=0)
        assert "pager.offset" not in params

    def test_search_sentinel_always_present(self):
        params = _build_params_1821(census_year=1841)
        assert params["search"] == "Search"

    def test_first_name_and_sex(self):
        params = _build_params_1821(census_year=1831, first_name="John", sex="Male")
        assert params["firstname"] == "John"
        assert params["sex"] == "Male"


class TestTableParser:
    def _html(self, rows: str) -> str:
        return (
            '<table class="results" summary="Search result table">'
            "<thead><tr><th>Surname</th><th>Forename</th></tr></thead>"
            f"<tbody>{rows}</tbody></table>"
        )

    def test_parses_odd_row(self):
        html = self._html(
            '<tr class="odd"><td><a href="/pages/1851/foo/">Murphy</a></td>'
            "<td><a href=\"/pages/1851/foo/\">Eliza</a></td></tr>"
        )
        parser = _TableParser()
        parser.feed(html)
        assert len(parser.rows) == 1
        cells, href = parser.rows[0]
        assert cells[0] == "Murphy"
        assert cells[1] == "Eliza"
        assert href == "/pages/1851/foo/"

    def test_parses_even_row(self):
        html = self._html(
            '<tr class="even"><td>Corrigan</td><td>James</td></tr>'
        )
        parser = _TableParser()
        parser.feed(html)
        assert len(parser.rows) == 1

    def test_ignores_thead_rows(self):
        html = self._html("")
        parser = _TableParser()
        parser.feed(html)
        assert parser.rows == []

    def test_multiple_rows(self):
        html = self._html(
            '<tr class="odd"><td>Murphy</td><td>John</td></tr>'
            '<tr class="even"><td>Corrigan</td><td>Mary</td></tr>'
        )
        parser = _TableParser()
        parser.feed(html)
        assert len(parser.rows) == 2
        assert parser.rows[0][0][0] == "Murphy"
        assert parser.rows[1][0][0] == "Corrigan"

    def test_ignores_non_result_table(self):
        html = '<table class="other"><tr class="odd"><td>Murphy</td></tr></table>'
        parser = _TableParser()
        parser.feed(html)
        assert parser.rows == []

    def test_captures_first_href_in_row(self):
        html = self._html(
            '<tr class="odd">'
            '<td><a href="/pages/1821/detail/42/">Murphy</a></td>'
            '<td><a href="/pages/1821/detail/99/">Bernard</a></td>'
            "</tr>"
        )
        parser = _TableParser()
        parser.feed(html)
        _, href = parser.rows[0]
        assert href == "/pages/1821/detail/42/"


class TestParseRow1821_1851:
    def test_1851_full_row(self):
        # Surname, Forename, Townland, FamilyID, Barony, Parish, County,
        # Age, Sex, AgeMonths, Relation, MaritalStatus, MarriageYears,
        # Occupation, Education, NativeCountry, CauseOfDeath, YearOfDeath
        cells = [
            "Murphy", "Eliza", "Montiaghs", "39", "Upper Massereene",
            "Aghagallon", "Antrim", "43", "Female", "-",
            "Daughter", "Married", "1830", "Sewing", "Read & Write",
            "Antrim", "-", "-",
        ]
        r = _parse_row(cells, "/pages/1851/foo/", 1851)
        assert r.census_year == 1851
        assert r.surname == "Murphy"
        assert r.first_name == "Eliza"
        assert r.townland_street == "Montiaghs"
        assert r.ded == "Aghagallon"        # parish
        assert r.county == "Antrim"
        assert r.age == 43
        assert r.sex == "Female"
        assert r.relationship == "Daughter"
        assert r.marital_status == "Married"
        assert r.occupation == "Sewing"
        assert r.birthplace == "Antrim"
        assert r.detail_url == BASE_URL + "/pages/1851/foo/"

    def test_1841_same_columns_as_1851(self):
        cells = [
            "Corrigan", "Catherine", "Some Street", "-", "-",
            "Kilkenny Parish", "Kilkenny", "70", "Female", "-",
            "Visitor", "Widow", "-", "?", "Cannot Read", "?", "-", "-",
        ]
        r = _parse_row(cells, "", 1841)
        assert r.census_year == 1841
        assert r.age == 70
        assert r.sex == "Female"
        assert r.relationship == "Visitor"
        assert r.marital_status == "Widow"
        # "?" is treated as empty
        assert r.occupation == ""
        assert r.birthplace == ""

    def test_1831_row(self):
        # Surname, Forename, Townland, House#, Barony, Parish, County, + hidden stats
        cells = ["Corrigan", "Robt", "Bishop Street", "109", "-", "Templemore", "-"]
        r = _parse_row(cells, "/pages/1831/foo/", 1831)
        assert r.census_year == 1831
        assert r.surname == "Corrigan"
        assert r.first_name == "Robt"
        assert r.townland_street == "Bishop Street"
        assert r.ded == "Templemore"    # parish
        assert r.county == ""           # "-" normalised to ""
        assert r.age is None
        assert r.sex == ""

    def test_1821_row(self):
        # Surname, Forename, Townland, House#, Parish, County, Age, Occupation*, Relation*
        cells = ["Murphy", "Bernard", "Manorland, River Boyne", "72", "Trim", "Meath", "39",
                 "Day Labourer", "Head"]
        r = _parse_row(cells, "/pages/1821/foo/", 1821)
        assert r.census_year == 1821
        assert r.surname == "Murphy"
        assert r.first_name == "Bernard"
        assert r.townland_street == "Manorland, River Boyne"
        assert r.ded == "Trim"          # parish
        assert r.county == "Meath"
        assert r.age == 39
        assert r.occupation == "Day Labourer"
        assert r.relationship == "Head"

    def test_dash_values_normalised_to_empty(self):
        cells = ["Murphy", "-", "-", "-", "-", "-", "-"]
        r = _parse_row(cells, "", 1831)
        assert r.first_name == ""
        assert r.county == ""

    def test_detail_url_none_when_no_href(self):
        cells = ["Murphy", "John", "Main St", "-", "-", "Parish", "Cork"]
        r = _parse_row(cells, "", 1831)
        assert r.detail_url is None

    def test_short_row_does_not_raise(self):
        """Rows with fewer cells than expected should not raise IndexError."""
        cells = ["Murphy"]
        r = _parse_row(cells, "", 1851)
        assert r.surname == "Murphy"
        assert r.age is None


# ---------------------------------------------------------------------------
# WarOfficeSearcher helpers
# ---------------------------------------------------------------------------

class TestWarOfficeSearcher:
    def test_normalise_regiment_strips_depot(self):
        assert _normalise_regiment("Royal Garrison Artillery Depot") == "Royal Garrison Artillery"

    def test_normalise_regiment_strips_reserve(self):
        assert _normalise_regiment("Royal Irish Regiment Reserve") == "Royal Irish Regiment"

    def test_normalise_regiment_strips_tf(self):
        assert _normalise_regiment("Royal Garrison Artillery T.F.") == "Royal Garrison Artillery"

    def test_normalise_regiment_clean_name_unchanged(self):
        assert _normalise_regiment("Royal Irish Regiment") == "Royal Irish Regiment"
