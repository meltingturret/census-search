"""Shared fixtures for census-search tests."""

import pytest

from census_search.models import CensusRecord, SearchResult


@pytest.fixture
def record_1926():
    return CensusRecord(
        census_year=1926,
        surname="Corrigan",
        first_name="James",
        age=46,
        sex="Male",
        county="Kilkenny",
        townland_street="High Street",
        ded="Kilkenny Urban",
        occupation="Labourer",
        birthplace="Kilkenny",
    )


@pytest.fixture
def record_1911():
    return CensusRecord(
        census_year=1911,
        surname="Corrigan",
        first_name="James",
        age=31,
        sex="Male",
        county="Kilkenny",
        townland_street="High Street",
        ded="Kilkenny Urban",
    )


@pytest.fixture
def record_1901():
    return CensusRecord(
        census_year=1901,
        surname="Corrigan",
        first_name="James",
        age=21,
        sex="Male",
        county="Kilkenny",
    )


@pytest.fixture
def result_1911(record_1911):
    return SearchResult(
        census_year=1911,
        total=1,
        records=[record_1911],
        search_url="https://example.com/1911",
    )


@pytest.fixture
def result_1901(record_1901):
    return SearchResult(
        census_year=1901,
        total=1,
        records=[record_1901],
        search_url="https://example.com/1901",
    )
