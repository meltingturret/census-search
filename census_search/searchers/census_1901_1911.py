"""Searcher for the 1901 and 1911 Irish Censuses."""

from __future__ import annotations

from typing import Optional
from urllib.parse import urlencode

import httpx

from census_search.models import CensusRecord, SearchResult

API_BASE = "https://api-census.nationalarchives.ie/census/query"
PAGE_SIZE = 30


def _build_params(
    surname: str = "",
    first_name: str = "",
    county: str = "",
    sex: str = "",
    census_year: Optional[int] = None,
    age_from: Optional[int] = None,
    age_to: Optional[int] = None,
    exact: bool = False,
    limit: int = PAGE_SIZE,
    offset: int = 0,
) -> dict:
    params: dict[str, str | int] = {"limit": limit}
    if offset:
        params["offset"] = offset
    if census_year:
        params["census_year"] = census_year
    if county:
        params["county"] = county
    if sex:
        params["sex"] = sex
    if surname:
        params["surname__iexact" if exact else "surname__icontains"] = surname
    if first_name:
        params["firstname__icontains"] = first_name
    if age_from is not None:
        params["age__gte"] = age_from
    if age_to is not None:
        params["age__lte"] = age_to
    return params


def _parse_record(row: dict, fallback_year: int) -> CensusRecord:
    def _int(v) -> Optional[int]:
        try:
            return int(v)
        except (TypeError, ValueError):
            return None

    return CensusRecord(
        census_year=row.get("census_year") or fallback_year,
        surname=row.get("surname") or "",
        first_name=row.get("firstname") or "",
        age=_int(row.get("age")),
        sex=row.get("sex") or "",
        county=row.get("county") or "",
        townland_street=row.get("townland") or "",
        ded=row.get("ded") or "",
        relationship=row.get("relation_to_head_updated") or row.get("relation_to_head") or "",
        religion=row.get("religion_updated") or row.get("religion") or "",
        occupation=row.get("occupation_updated") or row.get("occupation") or "",
        marital_status=row.get("marriage_status") or "",
        birthplace=row.get("birthplace") or "",
        irish_language=row.get("language_updated") or row.get("language") or "",
        detail_url=None,
    )


class Census1901_1911Searcher:
    """Search the 1901 and 1911 Irish Censuses via the REST API."""

    async def __aenter__(self):
        self._client = httpx.AsyncClient(timeout=30)
        return self

    async def __aexit__(self, *args):
        await self._client.aclose()

    async def search(
        self,
        surname: str = "",
        first_name: str = "",
        county: str = "",
        sex: str = "",
        census_year: Optional[int] = None,
        age_from: Optional[int] = None,
        age_to: Optional[int] = None,
        exact: bool = False,
        max_results: int = 100,
    ) -> SearchResult:
        params = _build_params(
            surname=surname,
            first_name=first_name,
            county=county,
            sex=sex,
            census_year=census_year,
            age_from=age_from,
            age_to=age_to,
            exact=exact,
            limit=min(PAGE_SIZE, max_results),
        )

        records: list[CensusRecord] = []
        total = 0
        next_qs: Optional[str] = None

        try:
            resp = await self._client.get(API_BASE, params=params)
            resp.raise_for_status()
            data = resp.json()
            records, total, next_qs = self._parse_response(data, census_year or 0)
        except Exception:
            pass

        # Paginate
        while next_qs and len(records) < max_results:
            try:
                next_url = API_BASE + (next_qs if next_qs.startswith("?") else "?" + next_qs)
                resp = await self._client.get(next_url)
                resp.raise_for_status()
                data = resp.json()
                new_records, _, next_qs = self._parse_response(data, census_year or 0)
                if not new_records:
                    break
                records.extend(new_records)
            except Exception:
                break

        search_url = API_BASE + "?" + urlencode({k: v for k, v in params.items()})
        return SearchResult(
            census_year=census_year or 0,
            total=total,
            records=records[:max_results],
            search_url=search_url,
        )

    async def search_both_years(
        self,
        surname: str,
        first_name: str = "",
        county: str = "",
        sex: str = "",
        birth_year: Optional[int] = None,
        age_tolerance: int = 3,
        exact: bool = False,
        max_results: int = 50,
    ) -> list[SearchResult]:
        results = []
        for year in [1901, 1911]:
            age_from, age_to = None, None
            if birth_year is not None:
                expected_age = year - birth_year
                age_from = max(0, expected_age - age_tolerance)
                age_to = expected_age + age_tolerance

            result = await self.search(
                surname=surname,
                first_name=first_name,
                county=county,
                sex=sex,
                census_year=year,
                age_from=age_from,
                age_to=age_to,
                exact=exact,
                max_results=max_results,
            )
            results.append(result)
        return results

    def _parse_response(
        self, data: dict, fallback_year: int
    ) -> tuple[list[CensusRecord], int, Optional[str]]:
        if not isinstance(data, dict):
            return [], 0, None
        meta = data.get("meta") or {}
        total = meta.get("count") or 0
        next_qs = meta.get("next")
        records = [_parse_record(row, fallback_year) for row in data.get("results", [])]
        return records, int(total), next_qs
