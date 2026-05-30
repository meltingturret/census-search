"""Links census records across years for the same individual."""

from __future__ import annotations

from typing import Optional

from census_search.models import CensusRecord, LinkedPerson, SearchResult

AGE_TOLERANCE = 3  # years either side when matching across censuses


def link_person(
    record_1926: CensusRecord,
    results_1901_1911: list[SearchResult],
) -> LinkedPerson:
    """
    Given a 1926 census record, find matching records in 1901/1911 results
    and return a LinkedPerson containing all found records.
    """
    all_records = [record_1926]
    birth_year = record_1926.birth_year_estimate

    for result in results_1901_1911:
        for candidate in result.records:
            if _is_likely_match(record_1926, candidate, birth_year):
                all_records.append(candidate)
                break  # Take best match per census year

    return LinkedPerson(name=record_1926.full_name, records=all_records)


def _is_likely_match(
    anchor: CensusRecord,
    candidate: CensusRecord,
    birth_year: Optional[int],
) -> bool:
    """Return True if candidate is likely the same person as anchor."""
    # Name must be a reasonable match
    if not _names_match(anchor.surname, candidate.surname):
        return False
    if anchor.first_name and candidate.first_name:
        if not _names_match(anchor.first_name, candidate.first_name):
            return False

    # Age must be consistent with birth year
    if birth_year and candidate.birth_year_estimate:
        if abs(candidate.birth_year_estimate - birth_year) > AGE_TOLERANCE:
            return False

    # Sex should match if available
    if anchor.sex and candidate.sex:
        if anchor.sex.lower()[0] != candidate.sex.lower()[0]:
            return False

    return True


def _names_match(a: str, b: str) -> bool:
    """Case-insensitive name comparison, allowing for spelling variants."""
    a, b = a.strip().lower(), b.strip().lower()
    if not a or not b:
        return True
    # Exact match
    if a == b:
        return True
    # One starts with the other (handles abbreviations: "Pat" vs "Patrick")
    if a.startswith(b) or b.startswith(a):
        return True
    return False


def score_match(anchor: CensusRecord, candidate: CensusRecord) -> float:
    """
    Return a confidence score 0.0–1.0 for how likely candidate is
    the same person as anchor.
    """
    score = 0.0
    weight = 0.0

    # Surname (weight 3)
    if anchor.surname and candidate.surname:
        weight += 3
        if anchor.surname.lower() == candidate.surname.lower():
            score += 3
        elif _names_match(anchor.surname, candidate.surname):
            score += 1.5

    # First name (weight 2)
    if anchor.first_name and candidate.first_name:
        weight += 2
        if anchor.first_name.lower() == candidate.first_name.lower():
            score += 2
        elif _names_match(anchor.first_name, candidate.first_name):
            score += 1

    # Age consistency (weight 3)
    if anchor.birth_year_estimate and candidate.birth_year_estimate:
        weight += 3
        diff = abs(anchor.birth_year_estimate - candidate.birth_year_estimate)
        if diff == 0:
            score += 3
        elif diff <= 1:
            score += 2
        elif diff <= AGE_TOLERANCE:
            score += 1

    # County (weight 1)
    if anchor.county and candidate.county:
        weight += 1
        if anchor.county.lower() == candidate.county.lower():
            score += 1

    # Sex (weight 1)
    if anchor.sex and candidate.sex:
        weight += 1
        if anchor.sex.lower()[0] == candidate.sex.lower()[0]:
            score += 1

    return score / weight if weight > 0 else 0.0
