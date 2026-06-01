"""Data models for census records."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class CensusRecord(BaseModel):
    """A single person's census record."""

    census_year: int
    surname: str = ""
    first_name: str = ""
    age: Optional[int] = None
    sex: str = ""
    county: str = ""
    townland_street: str = ""
    ded: str = ""  # District Electoral Division
    relationship: str = ""
    religion: str = ""
    occupation: str = ""
    marital_status: str = ""
    birthplace: str = ""
    irish_language: str = ""
    detail_url: Optional[str] = None
    form_id: Optional[str] = None  # 1926 household form identifier (aform_name)

    @property
    def birth_year_estimate(self) -> Optional[int]:
        if self.age is not None:
            return self.census_year - self.age
        return None

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.surname}".strip()


class SearchResult(BaseModel):
    """Results from a census search."""

    census_year: int
    total: int
    records: list[CensusRecord]
    search_url: str = ""


class MilitaryRecord(BaseModel):
    """A British Army service, medal, or pension record from TNA Discovery."""

    reference: str = ""        # e.g. WO 372/5/31914
    series: str = ""           # e.g. WO 372
    record_type: str = ""      # "Medal card" | "Service record" | "Widow's pension" | "Pension file"
    title: str = ""
    regiment: str = ""
    service_number: str = ""
    rank: str = ""
    cause_of_death: str = ""   # PIN 82 — cause of death leading to widow's pension
    disability: str = ""       # PIN 26 — nature of disability
    dates: str = ""
    detail_url: Optional[str] = None


class LinkedPerson(BaseModel):
    """A person linked across multiple census years."""

    name: str
    records: list[CensusRecord]

    @property
    def census_years(self) -> list[int]:
        return sorted({r.census_year for r in self.records})

    @property
    def estimated_birth_year(self) -> Optional[int]:
        estimates = [r.birth_year_estimate for r in self.records if r.birth_year_estimate]
        if not estimates:
            return None
        return round(sum(estimates) / len(estimates))
