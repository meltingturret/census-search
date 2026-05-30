"""Searcher for the 1926 Irish Census."""

from __future__ import annotations

import re
from typing import Optional
from urllib.parse import urlencode, urlparse

from playwright.async_api import Page

from census_search.models import CensusRecord, SearchResult
from census_search.searchers.base import PlaywrightSearcher

SEARCH_BASE = "https://nationalarchives.ie/collections/search-the-1926-census/search-results/"

# Known API pattern — discovered by intercepting network requests.
# The site calls a backend API; we capture it at runtime.
API_PATTERN = "/api/"

COUNTIES = [
    "Carlow", "Cavan", "Clare", "Cork", "Donegal", "Dublin",
    "Galway", "Kerry", "Kildare", "Kilkenny", "Laois", "Leitrim",
    "Limerick", "Longford", "Louth", "Mayo", "Meath", "Monaghan",
    "Offaly", "Roscommon", "Sligo", "Tipperary", "Waterford",
    "Westmeath", "Wexford", "Wicklow",
]


def _build_search_url(
    surname: str = "",
    first_name: str = "",
    county: str = "",
    townland: str = "",
    ded: str = "",
    sex: str = "",
    exact: bool = False,
) -> str:
    params: dict[str, str] = {}
    if surname:
        params["surname"] = surname
    if first_name:
        params["firstname"] = first_name
    if county:
        params["county"] = county
    if townland:
        params["townland"] = townland
    if ded:
        params["ded"] = ded
    if sex:
        params["sex"] = sex
    if exact:
        params["exact"] = "true"
    return SEARCH_BASE + ("?" + urlencode(params) if params else "")


def _normalize_sex(raw: str) -> str:
    """Normalise 1926 API sex codes ('M'/'F') to full words for consistent filtering."""
    v = raw.strip().upper()
    if v == "M":
        return "Male"
    if v == "F":
        return "Female"
    return raw


def _parse_record_from_row(row_data: dict) -> CensusRecord:
    """Parse a record dict from the intercepted API response."""

    def _int(v) -> Optional[int]:
        try:
            return int(v)
        except (TypeError, ValueError):
            return None

    return CensusRecord(
        census_year=1926,
        surname=row_data.get("surname") or row_data.get("Surname") or "",
        first_name=row_data.get("first_name") or row_data.get("firstname") or row_data.get("FirstName") or "",
        age=_int(row_data.get("updated_age") or row_data.get("age") or row_data.get("Age")),
        sex=_normalize_sex(row_data.get("updated_sex") or row_data.get("sex") or row_data.get("Sex") or ""),
        county=row_data.get("county") or row_data.get("County") or "",
        townland_street=row_data.get("townland") or row_data.get("townland_street") or row_data.get("Townland") or "",
        ded=row_data.get("ded") or row_data.get("DED") or "",
        relationship=(
            row_data.get("relationship_to_head") or row_data.get("updated_relationship_to_head")
            or row_data.get("relationship") or row_data.get("RelationshipToHead") or ""
        ),
        religion=row_data.get("updated_religion") or row_data.get("religion") or row_data.get("Religion") or "",
        occupation=row_data.get("occupation") or row_data.get("PersonalOccupation") or "",
        marital_status=(
            row_data.get("updated_marriage") or row_data.get("marital_status") or row_data.get("MaritalStatus") or ""
        ),
        birthplace=(
            row_data.get("birthplace_county") or row_data.get("birthplace") or row_data.get("BirthplaceCounty") or ""
        ),
        irish_language=(
            row_data.get("updated_irish_language") or row_data.get("irish_language")
            or row_data.get("IrishLanguage") or ""
        ),
        detail_url=row_data.get("url") or row_data.get("detail_url") or None,
        form_id=(
            str(v) if (v := (
                row_data.get("aform_name") or row_data.get("image_group")
                or row_data.get("form_id") or row_data.get("household_id") or row_data.get("hhid")
            )) else None
        ),
    )


def _parse_records_from_dom(rows: list[dict]) -> list[CensusRecord]:
    return [_parse_record_from_row(r) for r in rows]


class Census1926Searcher(PlaywrightSearcher):
    """
    Search the 1926 Irish Census at nationalarchives.ie.

    Uses Playwright to handle the JavaScript-rendered search page,
    intercepting the underlying API calls for reliable data extraction.
    """

    # Cache the discovered API base URL and next-page cursor after first successful intercept
    _api_base_url: Optional[str] = None
    _next_qs: Optional[str] = None

    async def search(
        self,
        surname: str = "",
        first_name: str = "",
        county: str = "",
        townland: str = "",
        ded: str = "",
        sex: str = "",
        exact: bool = False,
        max_results: int = 100,
    ) -> SearchResult:
        url = _build_search_url(surname, first_name, county, townland, ded, sex, exact)
        page = await self._new_page()
        records: list[CensusRecord] = []
        total = 0

        try:
            api_url, data = await self._intercept_api_call(
                page, url, API_PATTERN, wait_selector=".search-results, [data-results], table"
            )

            if data is None:
                # Fallback: parse DOM if API interception failed
                records, total = await self._parse_dom_results(page)
            else:
                records, total, next_qs = self._parse_api_response(data)
                if api_url:
                    Census1926Searcher._api_base_url = api_url
                    Census1926Searcher._next_qs = next_qs

        finally:
            await page.close()

        # Paginate using meta.next cursor
        if total > len(records) and len(records) < max_results and Census1926Searcher._api_base_url:
            more = await self._fetch_remaining_pages(
                already_fetched=len(records), total=total, max_results=max_results
            )
            records.extend(more)

        return SearchResult(
            census_year=1926,
            total=total,
            records=records[:max_results],
            search_url=url,
        )

    def _parse_api_response(self, data: dict | list) -> tuple[list[CensusRecord], int, Optional[str]]:
        """
        Parse the API JSON response.
        Returns (records, total, next_page_querystring).
        """
        records: list[CensusRecord] = []
        total = 0
        next_qs: Optional[str] = None

        if isinstance(data, dict):
            meta = data.get("meta") or {}
            items = (
                data.get("results")
                or data.get("data")
                or data.get("records")
                or data.get("hits", {}).get("hits", [])
                or []
            )
            total = (
                meta.get("count")
                or data.get("total")
                or data.get("count")
                or data.get("hits", {}).get("total", {}).get("value", 0)
                or len(items)
            )
            next_qs = meta.get("next")
            for item in items:
                row = item.get("_source", item) if isinstance(item, dict) else {}
                records.append(_parse_record_from_row(row))

        elif isinstance(data, list):
            total = len(data)
            for item in data:
                records.append(_parse_record_from_row(item))

        return records, int(total), next_qs

    async def _parse_dom_results(self, page: Page) -> tuple[list[CensusRecord], int]:
        """Fallback: extract results from rendered DOM."""
        records: list[CensusRecord] = []

        # Try table rows
        rows = await page.query_selector_all("table tbody tr, [class*='result-row'], [class*='record-row']")
        for row in rows:
            cells = await row.query_selector_all("td, [class*='cell']")
            texts = [(await c.inner_text()).strip() for c in cells]
            if len(texts) >= 3:
                record = CensusRecord(
                    census_year=1926,
                    surname=texts[0] if len(texts) > 0 else "",
                    first_name=texts[1] if len(texts) > 1 else "",
                    age=_safe_int(texts[2]) if len(texts) > 2 else None,
                    sex=texts[3] if len(texts) > 3 else "",
                    county=texts[4] if len(texts) > 4 else "",
                    townland_street=texts[5] if len(texts) > 5 else "",
                    ded=texts[6] if len(texts) > 6 else "",
                )
                records.append(record)

        # Try to get total count
        total_el = await page.query_selector("[class*='total'], [class*='count'], [class*='showing']")
        total = len(records)
        if total_el:
            txt = await total_el.inner_text()
            m = re.search(r"(\d+)", txt)
            if m:
                total = int(m.group(1))

        return records, total

    async def _fetch_remaining_pages(
        self,
        already_fetched: int,
        total: int,
        max_results: int,
    ) -> list[CensusRecord]:
        """Fetch additional pages by following meta.next cursors."""
        import httpx

        if not Census1926Searcher._api_base_url:
            return []

        base = Census1926Searcher._api_base_url
        base_origin = f"{urlparse(base).scheme}://{urlparse(base).netloc}{urlparse(base).path}"
        next_qs = Census1926Searcher._next_qs
        records: list[CensusRecord] = []

        async with httpx.AsyncClient(timeout=30) as client:
            fetched = already_fetched
            while next_qs and fetched < min(total, max_results):
                # meta.next is a relative query string like "?county=Kilkenny&surname=Corrigan&offset=10"
                next_url = base_origin + (next_qs if next_qs.startswith("?") else "?" + next_qs)
                try:
                    resp = await client.get(next_url)
                    data = resp.json()
                    new_records, _, next_qs = self._parse_api_response(data)
                    if not new_records:
                        break
                    records.extend(new_records)
                    fetched += len(new_records)
                except Exception:
                    break

        return records


def _safe_int(s: str) -> Optional[int]:
    try:
        return int(s.strip())
    except (ValueError, AttributeError):
        return None
