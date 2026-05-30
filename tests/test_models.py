"""Tests for census_search.models."""

from census_search.models import CensusRecord, LinkedPerson, SearchResult

# ---------------------------------------------------------------------------
# CensusRecord
# ---------------------------------------------------------------------------

class TestCensusRecord:
    def test_birth_year_estimate_with_age(self):
        r = CensusRecord(census_year=1926, age=46)
        assert r.birth_year_estimate == 1880

    def test_birth_year_estimate_no_age(self):
        r = CensusRecord(census_year=1926)
        assert r.birth_year_estimate is None

    def test_birth_year_estimate_zero_age(self):
        r = CensusRecord(census_year=1926, age=0)
        assert r.birth_year_estimate == 1926

    def test_full_name_both(self):
        r = CensusRecord(census_year=1926, surname="Murphy", first_name="John")
        assert r.full_name == "John Murphy"

    def test_full_name_surname_only(self):
        r = CensusRecord(census_year=1926, surname="Murphy")
        assert r.full_name == "Murphy"

    def test_full_name_first_only(self):
        r = CensusRecord(census_year=1926, first_name="John")
        assert r.full_name == "John"

    def test_full_name_empty(self):
        r = CensusRecord(census_year=1926)
        assert r.full_name == ""

    def test_defaults(self):
        r = CensusRecord(census_year=1901)
        assert r.surname == ""
        assert r.first_name == ""
        assert r.age is None
        assert r.sex == ""
        assert r.county == ""
        assert r.detail_url is None

    def test_all_fields(self):
        r = CensusRecord(
            census_year=1926,
            surname="Corrigan",
            first_name="James",
            age=46,
            sex="Male",
            county="Kilkenny",
            townland_street="High Street",
            ded="Kilkenny Urban",
            relationship="Head",
            religion="Roman Catholic",
            occupation="Labourer",
            marital_status="Married",
            birthplace="Kilkenny",
            irish_language="Irish and English",
            detail_url="https://example.com/record/1",
        )
        assert r.birth_year_estimate == 1880
        assert r.full_name == "James Corrigan"
        assert r.detail_url == "https://example.com/record/1"

    def test_birth_year_1901(self):
        r = CensusRecord(census_year=1901, age=21)
        assert r.birth_year_estimate == 1880

    def test_birth_year_1911(self):
        r = CensusRecord(census_year=1911, age=31)
        assert r.birth_year_estimate == 1880


# ---------------------------------------------------------------------------
# SearchResult
# ---------------------------------------------------------------------------

class TestSearchResult:
    def test_basic(self):
        records = [CensusRecord(census_year=1926, surname="Murphy", age=40)]
        r = SearchResult(census_year=1926, total=1, records=records)
        assert r.total == 1
        assert len(r.records) == 1

    def test_empty(self):
        r = SearchResult(census_year=1926, total=0, records=[])
        assert r.total == 0
        assert r.records == []

    def test_search_url_default(self):
        r = SearchResult(census_year=1926, total=0, records=[])
        assert r.search_url == ""

    def test_multiple_records(self):
        records = [
            CensusRecord(census_year=1926, surname="Murphy", first_name="John", age=40),
            CensusRecord(census_year=1926, surname="Murphy", first_name="Mary", age=35),
        ]
        r = SearchResult(census_year=1926, total=2, records=records, search_url="https://example.com")
        assert r.total == 2
        assert r.records[0].first_name == "John"
        assert r.records[1].first_name == "Mary"


# ---------------------------------------------------------------------------
# LinkedPerson
# ---------------------------------------------------------------------------

class TestLinkedPerson:
    def test_census_years_sorted(self, record_1926, record_1911, record_1901):
        lp = LinkedPerson(
            name="James Corrigan",
            records=[record_1926, record_1901, record_1911],  # deliberately unsorted
        )
        assert lp.census_years == [1901, 1911, 1926]

    def test_census_years_deduped(self, record_1926):
        r2 = CensusRecord(census_year=1926, surname="Murphy", age=30)
        lp = LinkedPerson(name="Test", records=[record_1926, r2])
        assert lp.census_years == [1926]

    def test_estimated_birth_year_single(self, record_1926):
        # record_1926: age=46, census_year=1926 → birth=1880
        lp = LinkedPerson(name="James Corrigan", records=[record_1926])
        assert lp.estimated_birth_year == 1880

    def test_estimated_birth_year_average(self, record_1926, record_1911, record_1901):
        # 1926-46=1880, 1911-31=1880, 1901-21=1880 → all agree
        lp = LinkedPerson(
            name="James Corrigan",
            records=[record_1926, record_1911, record_1901],
        )
        assert lp.estimated_birth_year == 1880

    def test_estimated_birth_year_with_variance(self):
        # Simulate slight age rounding across years
        records = [
            CensusRecord(census_year=1926, age=46),  # → 1880
            CensusRecord(census_year=1911, age=30),  # → 1881
            CensusRecord(census_year=1901, age=20),  # → 1881
        ]
        lp = LinkedPerson(name="Test", records=records)
        # average of [1880, 1881, 1881] = 1880.67 → rounds to 1881
        assert lp.estimated_birth_year == 1881

    def test_estimated_birth_year_no_ages(self):
        records = [CensusRecord(census_year=1926), CensusRecord(census_year=1911)]
        lp = LinkedPerson(name="Test", records=records)
        assert lp.estimated_birth_year is None

    def test_estimated_birth_year_some_missing(self):
        records = [
            CensusRecord(census_year=1926, age=46),  # → 1880
            CensusRecord(census_year=1911),           # no age
        ]
        lp = LinkedPerson(name="Test", records=records)
        assert lp.estimated_birth_year == 1880
