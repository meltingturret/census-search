"""Tests for census searcher parsing logic (no browser required)."""

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
