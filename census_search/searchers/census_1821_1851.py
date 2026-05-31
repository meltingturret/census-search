"""Searcher for the 1821, 1831, 1841, and 1851 Irish Census fragments.

Source: https://www.census.nationalarchives.ie/search/results.jsp
These are partial/fragment censuses — not all counties or returns survived.
"""

from __future__ import annotations

from html.parser import HTMLParser
from typing import Optional
from urllib.parse import urlencode

import httpx

from census_search.models import CensusRecord, SearchResult

BASE_URL = "https://www.census.nationalarchives.ie"
SEARCH_URL = f"{BASE_URL}/search/results.jsp"
PAGE_SIZE = 100

VALID_YEARS = (1821, 1831, 1841, 1851)


class _TableParser(HTMLParser):
    """Extract rows from the <table class="results"> element."""

    def __init__(self):
        super().__init__()
        self._in_table = False
        self._in_cell = False
        self._current_row: list[str] = []
        self._current_cell: list[str] = []
        self._current_link: str = ""
        self.rows: list[tuple[list[str], str]] = []  # (cells, detail_href)
        self._row_href = ""

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "table" and "result" in (attrs.get("class") or ""):
            self._in_table = True
        if not self._in_table:
            return
        if tag == "tr" and attrs.get("class") in ("odd", "even"):
            self._current_row = []
            self._row_href = ""
        if tag == "td":
            self._in_cell = True
            self._current_cell = []
        if tag == "a" and self._in_cell and not self._row_href:
            self._row_href = attrs.get("href", "")

    def handle_endtag(self, tag):
        if not self._in_table:
            return
        if tag == "td":
            self._in_cell = False
            self._current_row.append("".join(self._current_cell).strip())
        if tag == "tr" and self._current_row:
            self.rows.append((self._current_row[:], self._row_href))
            self._current_row = []
        if tag == "table":
            self._in_table = False

    def handle_data(self, data):
        if self._in_cell:
            self._current_cell.append(data)


def _clean(v: str) -> str:
    v = v.strip()
    return "" if v in ("-", "?", "N/A") else v


def _int(v: str) -> Optional[int]:
    try:
        return int(v.strip())
    except (ValueError, TypeError):
        return None


def _parse_row(cells: list[str], href: str, year: int) -> CensusRecord:
    """Map a result-table row to a CensusRecord. Column layout varies by year."""
    c = cells  # shorthand

    def g(i: int) -> str:
        return _clean(c[i]) if i < len(c) else ""

    detail_url = BASE_URL + href if href else None

    if year == 1821:
        # Surname, Forename, Townland/Street, House#, Parish, County, Age, Occupation*, Relation*
        return CensusRecord(
            census_year=year,
            surname=g(0),
            first_name=g(1),
            townland_street=g(2),
            ded=g(4),        # Parish
            county=g(5),
            age=_int(g(6)),
            occupation=g(7),
            relationship=g(8),
            detail_url=detail_url,
        )

    if year == 1831:
        # Surname, Forename, Townland/Street, House#, Barony, Parish, County, + hidden household stats
        return CensusRecord(
            census_year=year,
            surname=g(0),
            first_name=g(1),
            townland_street=g(2),
            ded=g(5),        # Parish
            county=g(6),
            detail_url=detail_url,
        )

    # 1841 and 1851 share the same column layout:
    # Surname, Forename, Townland/Street, Family ID, Barony, Parish, County,
    # Age, Sex, Age-in-months, Relation, Marital status, Marriage years,
    # Occupation, Education, Native country, Cause of death, Year of death
    return CensusRecord(
        census_year=year,
        surname=g(0),
        first_name=g(1),
        townland_street=g(2),
        ded=g(5),            # Parish
        county=g(6),
        age=_int(g(7)),
        sex=g(8),
        relationship=g(10),
        marital_status=g(11),
        occupation=g(13),
        birthplace=g(15),
        detail_url=detail_url,
    )


def _build_params(
    census_year: int,
    surname: str = "",
    first_name: str = "",
    county: str = "",
    sex: str = "",
    page_size: int = PAGE_SIZE,
    offset: int = 0,
) -> dict:
    params: dict = {
        "census_year": census_year,
        "surname": surname,
        "firstname": first_name,
        "sex": sex,
        "search": "Search",
        "pageSize": page_size,
        "searchMoreVisible": "false",
    }
    # County param name is year-specific
    params[f"county{census_year}"] = county
    if offset:
        params["pager.offset"] = offset
    return params


class Census1821_1851Searcher:
    """Scrape the National Archives census fragment search for 1821–1851."""

    async def __aenter__(self):
        self._client = httpx.AsyncClient(timeout=30, follow_redirects=True)
        return self

    async def __aexit__(self, *args):
        await self._client.aclose()

    async def search(
        self,
        census_year: int,
        surname: str = "",
        first_name: str = "",
        county: str = "",
        sex: str = "",
        max_results: int = 100,
    ) -> SearchResult:
        if census_year not in VALID_YEARS:
            raise ValueError(f"census_year must be one of {VALID_YEARS}")

        records: list[CensusRecord] = []
        offset = 0

        while len(records) < max_results:
            batch_size = min(PAGE_SIZE, max_results - len(records))
            params = _build_params(
                census_year=census_year,
                surname=surname,
                first_name=first_name,
                county=county,
                sex=sex,
                page_size=batch_size,
                offset=offset,
            )
            try:
                resp = await self._client.get(SEARCH_URL, params=params)
                resp.raise_for_status()
            except Exception:
                break

            parser = _TableParser()
            parser.feed(resp.text)

            if not parser.rows:
                break

            for cells, href in parser.rows:
                records.append(_parse_row(cells, href, census_year))

            if len(parser.rows) < batch_size:
                break  # last page
            offset += batch_size

        search_url = SEARCH_URL + "?" + urlencode(_build_params(
            census_year=census_year,
            surname=surname,
            first_name=first_name,
            county=county,
            sex=sex,
        ))
        return SearchResult(
            census_year=census_year,
            total=len(records),
            records=records[:max_results],
            search_url=search_url,
        )
