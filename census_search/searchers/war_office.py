"""Searcher for British Army records via TNA Discovery API.

Source: https://discovery.nationalarchives.gov.uk/API
No authentication required. Series searched:

  WO 372 — WWI Medal Index Cards (individual, digitised)
  WO 97  — Victorian/Edwardian Service Records (individual, birthplace included)
  PIN 82 — WWI Widows' Pension Forms (individual, implies widow dependent)
  PIN 26 — Ministry of Pensions files (individual, disability + widow/dependant files)
"""

from __future__ import annotations

import asyncio
import re

import httpx

from census_search.models import MilitaryRecord

# Suffixes appended to regiment names in WO 372 corpBodies that are not present
# in PIN 82/PIN 26 unit fields.  Strip them before building the pension query.
_REGIMENT_SUFFIX_RE = re.compile(
    r"\b(Depot|Reserve|Territorial Force|T\.?F\.?|Garrison Battalion|"
    r"Labour Battalion|Home Service|Provisional Battalion)\b.*$",
    re.IGNORECASE,
)


def _normalise_regiment(regiment: str) -> str:
    """Strip administrative suffixes so WO 372 regiment names match PIN 82 unit names."""
    return _REGIMENT_SUFFIX_RE.sub("", regiment).strip().rstrip(",")


API_BASE = "https://discovery.nationalarchives.gov.uk/API"
RECORD_URL = "https://discovery.nationalarchives.gov.uk/details/r"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; census-search/1.0)"}

# (series_code, record_type_label)
SERIES = [
    ("WO 372", "Medal card"),
    ("WO 97",  "Service record"),
    ("PIN 82", "Widow's pension"),
    ("PIN 26", "Pension file"),
]


def _parse_wo372(desc: str, corps: list[str]) -> tuple[str, str, str, str, str]:
    """Return (regiment, service_number, rank, cause_of_death, disability)."""
    regiment = ", ".join(corps) if corps else ""
    service_number = ""
    rank = ""
    m = re.search(r"\b(\d{3,6})\b", desc)
    if m:
        service_number = m.group(1)
    m = re.search(r"\b\d{3,6}\s+([A-Z][a-zA-Z\s]+?)\.?\s*$", desc)
    if m:
        rank = m.group(1).strip()
    return regiment, service_number, rank, "", ""


def _parse_wo97(desc: str, corps: list[str]) -> tuple[str, str, str, str, str]:
    """Return (regiment, service_number, rank, cause_of_death, disability)."""
    regiment = ", ".join(corps) if corps else ""
    rank = ""
    if not regiment:
        m = re.search(r"Served in (.+?)(?:Discharged|$)", desc, re.IGNORECASE)
        if m:
            regiment = m.group(1).strip()
    m = re.search(r"Discharged aged (\d+)", desc, re.IGNORECASE)
    if m:
        rank = f"Discharged aged {m.group(1)}"
    return regiment, "", rank, "", ""


def _parse_pin82(desc: str, corps: list[str]) -> tuple[str, str, str, str, str]:
    """Return (regiment, service_number, rank, cause_of_death, disability).

    PIN 82 title format:
    "Name: James CORRIGAN. Unit: Royal Garrison Artillery. Cause of death: Phthisis pulmonalis."
    """
    regiment = ", ".join(corps) if corps else ""
    cause = ""
    if not regiment:
        m = re.search(r"Unit:\s*(.+?)(?:\.|Cause|$)", desc, re.IGNORECASE)
        if m:
            regiment = m.group(1).strip()
    m = re.search(r"Cause of death:\s*(.+?)\.?\s*$", desc, re.IGNORECASE)
    if m:
        cause = m.group(1).strip()
    return regiment, "", "", cause, ""


def _parse_pin26(desc: str, corps: list[str]) -> tuple[str, str, str, str, str]:
    """Return (regiment, service_number, rank, cause_of_death, disability).

    PIN 26 format varies:
    "SURNAME, Firstname. Rank. Regiment. Nature of Disability: ..."
    or "Acting Sister ... QAIMNS (Reserve). Nature of Disability: ..."
    """
    regiment = ", ".join(corps) if corps else ""
    disability = ""
    rank = ""
    m = re.search(r"Nature of [Dd]isability:\s*(.+?)\.?\s*$", desc, re.IGNORECASE)
    if m:
        disability = m.group(1).strip()
    return regiment, "", rank, "", disability


_PARSERS = {
    "WO 372": _parse_wo372,
    "WO 97":  _parse_wo97,
    "PIN 82": _parse_pin82,
    "PIN 26": _parse_pin26,
}


def _parse_record(item: dict, series: str, record_type: str) -> MilitaryRecord:
    ref = item.get("reference", "")
    title = item.get("title", "")
    desc = item.get("description", "") or title
    corps = item.get("corpBodies") or []
    dates = item.get("coveringDates", "")
    tna_id = item.get("id", "")

    parser = _parsers_for(series)
    regiment, service_number, rank, cause_of_death, disability = parser(desc, corps)

    return MilitaryRecord(
        reference=ref,
        series=series,
        record_type=record_type,
        title=title,
        regiment=regiment,
        service_number=service_number,
        rank=rank,
        cause_of_death=cause_of_death,
        disability=disability,
        dates=dates,
        detail_url=f"{RECORD_URL}/{tna_id}" if tna_id else None,
    )


def _parsers_for(series: str):
    for key, fn in _PARSERS.items():
        if series.startswith(key):
            return fn
    return lambda desc, corps: ("", "", "", "", "")


class WarOfficeSearcher:
    """Search TNA Discovery API for WO 372, WO 97, PIN 82, and PIN 26."""

    async def __aenter__(self):
        self._client = httpx.AsyncClient(headers=HEADERS, timeout=30, follow_redirects=True)
        return self

    async def __aexit__(self, *args):
        await self._client.aclose()

    async def _query_series(
        self, series_code: str, record_type: str, query: str, max_results: int
    ) -> list[MilitaryRecord]:
        params = {
            "sps.searchQuery": query,
            "sps.recordSeries": series_code,
            "sps.resultsPageSize": max_results,
        }
        for attempt in range(3):
            try:
                resp = await self._client.get(f"{API_BASE}/search/v1/records", params=params)
                resp.raise_for_status()
                if not resp.content:
                    # TNA returns HTTP 202 with empty body when rate-limiting; back off and retry.
                    await asyncio.sleep(2 ** attempt * 3)
                    continue
                data = resp.json()
                return [_parse_record(item, series_code, record_type) for item in data.get("records", [])]
            except Exception:
                return []
        return []

    async def search(
        self,
        surname: str,
        first_name: str = "",
        service_number: str = "",
        regiment: str = "",
        max_results: int = 20,
    ) -> list[MilitaryRecord]:
        # Pass 1: service/medal series — include service number for precision.
        full_parts = [p for p in [first_name, surname, service_number, regiment] if p]
        full_query = " ".join(full_parts)

        service_records: list[MilitaryRecord] = []
        for series_code, record_type in SERIES:
            if series_code in ("WO 372", "WO 97"):
                service_records.extend(await self._query_series(series_code, record_type, full_query, max_results))
                await asyncio.sleep(1)

        # Pass 2: pension/dependant series — PIN 82/PIN 26 are indexed by name and
        # unit only (no service number).  Use the regiment discovered in pass 1 so
        # we don't pull in pension records for unrelated soldiers with the same name.
        found_regiment = regiment
        if not found_regiment and service_records:
            # Take the first non-empty regiment from the service results.
            for r in service_records:
                if r.regiment:
                    found_regiment = r.regiment
                    break

        # Strip admin suffixes (Depot, Reserve, T.F. …) so the pension query
        # matches the cleaner unit names used in PIN 82/PIN 26.
        pension_regiment = _normalise_regiment(found_regiment) if found_regiment else ""
        pension_parts = [p for p in [first_name, surname, pension_regiment] if p]
        pension_query = " ".join(pension_parts)

        pension_records: list[MilitaryRecord] = []
        for series_code, record_type in SERIES:
            if series_code in ("PIN 82", "PIN 26"):
                pension_records.extend(await self._query_series(series_code, record_type, pension_query, max_results))
                await asyncio.sleep(1)

        return service_records + pension_records
