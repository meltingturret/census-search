"""Links census records across years for the same individual."""

from __future__ import annotations

from typing import Optional

from census_search.models import CensusRecord, LinkedPerson, SearchResult
from census_search.phonetic import name_similarity, soundex

AGE_TOLERANCE = 3  # years either side when matching across censuses

# Minimum score to count as a match when using score_match
MATCH_THRESHOLD = 0.40

# Relationship compatibility matrix — maps frozenset of two relationships to a
# 0.0–1.0 plausibility score.  Same relationship always scores 1.0 (handled
# separately).  Only pairs that make historical sense are listed; everything
# else defaults to 0.2 (unlikely but not impossible).
_REL_COMPAT: dict[frozenset, float] = {
    frozenset({"son", "scholar"}): 0.85,
    frozenset({"daughter", "scholar"}): 0.85,
    frozenset({"son", "boarder"}): 0.65,
    frozenset({"daughter", "servant"}): 0.65,
    frozenset({"head", "son"}): 0.55,      # grew up to become head
    frozenset({"head", "boarder"}): 0.45,
    frozenset({"wife", "daughter"}): 0.40,  # married between census years
    frozenset({"wife", "servant"}): 0.35,
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def link_person(
    record_1926: CensusRecord,
    results_1901_1911: list[SearchResult],
) -> LinkedPerson:
    """Given a 1926 census record, find the best-matching record in each
    1901/1911 result set and return a LinkedPerson containing all found records.

    Candidates are ranked by score_match; only those above MATCH_THRESHOLD
    are included.
    """
    all_records = [record_1926]

    for result in results_1901_1911:
        match = best_scored_match(record_1926, result)
        if match:
            all_records.append(match[0])

    return LinkedPerson(name=record_1926.full_name, records=all_records)


def best_scored_match(
    anchor: CensusRecord,
    result: SearchResult,
) -> tuple[CensusRecord, float] | None:
    """Return (best_candidate, confidence_0_to_1) or None if no candidate
    clears MATCH_THRESHOLD.

    Candidates from *result* are ranked by score_match and the highest scorer
    is returned.
    """
    if not result.records:
        return None

    scored = [
        (candidate, score_match(anchor, candidate))
        for candidate in result.records
    ]
    scored.sort(key=lambda x: x[1], reverse=True)
    best_rec, best_score = scored[0]
    if best_score < MATCH_THRESHOLD:
        return None
    return best_rec, best_score


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def score_match(anchor: CensusRecord, candidate: CensusRecord) -> float:
    """Return a confidence score 0.0–1.0 for how likely *candidate* is the
    same person as *anchor*.

    Weights
    -------
    Surname         3  — exact, phonetic (Soundex), or fuzzy partial credit
    First name      2  — exact, prefix, or fuzzy partial credit
    Age consistency 3  — graded by years difference
    County          1  — exact match
    Sex             1  — first-letter comparison
    Relationship    1  — plausibility across census years
    """
    score = 0.0
    weight = 0.0

    # --- Surname (weight 3) ---
    if anchor.surname and candidate.surname:
        weight += 3
        score += _name_score(anchor.surname, candidate.surname) * 3

    # --- First name (weight 2) ---
    if anchor.first_name and candidate.first_name:
        weight += 2
        score += _name_score(anchor.first_name, candidate.first_name) * 2

    # --- Age consistency (weight 3) ---
    if anchor.birth_year_estimate and candidate.birth_year_estimate:
        weight += 3
        diff = abs(anchor.birth_year_estimate - candidate.birth_year_estimate)
        if diff == 0:
            score += 3
        elif diff <= 1:
            score += 2.5
        elif diff <= 2:
            score += 1.5
        elif diff <= AGE_TOLERANCE:
            score += 0.75

    # --- County (weight 1) ---
    if anchor.county and candidate.county:
        weight += 1
        if anchor.county.lower() == candidate.county.lower():
            score += 1

    # --- Sex (weight 1) ---
    if anchor.sex and candidate.sex:
        weight += 1
        if anchor.sex.lower()[0] == candidate.sex.lower()[0]:
            score += 1

    # --- Relationship (weight 1) ---
    if anchor.relationship and candidate.relationship:
        weight += 1
        score += _relationship_score(anchor.relationship, candidate.relationship)

    return score / weight if weight > 0 else 0.0


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _names_match(a: str, b: str) -> bool:
    """Return True if *a* and *b* are plausibly the same name.

    Checks (in order): exact, prefix/abbreviation, Soundex, high similarity.
    """
    a, b = a.strip().lower(), b.strip().lower()
    if not a or not b:
        return True
    if a == b:
        return True
    if a.startswith(b) or b.startswith(a):
        return True
    if soundex(a) == soundex(b):
        return True
    if name_similarity(a, b) >= 0.80:
        return True
    return False


def _name_score(a: str, b: str) -> float:
    """Return a 0.0–1.0 partial credit for how well two names match."""
    a_l, b_l = a.strip().lower(), b.strip().lower()
    if not a_l or not b_l:
        return 0.5  # unknown — neutral
    if a_l == b_l:
        return 1.0
    if a_l.startswith(b_l) or b_l.startswith(a_l):
        return 0.85
    if soundex(a_l) == soundex(b_l):
        return 0.70
    sim = name_similarity(a_l, b_l)
    if sim >= 0.80:
        return 0.60
    if sim >= 0.65:
        return 0.30
    return 0.0


def _relationship_score(rel_a: str, rel_b: str) -> float:
    """Return a 0.0–1.0 plausibility score for two relationship strings.

    Handles common Irish census variants (e.g. "Son" / "Scholar",
    "Daughter" / "Servant") that indicate the same person at different
    life stages.
    """
    if not rel_a or not rel_b:
        return 0.5  # unknown — neutral
    ra = rel_a.strip().lower()
    rb = rel_b.strip().lower()
    if ra == rb:
        return 1.0
    return _REL_COMPAT.get(frozenset({ra, rb}), 0.20)


def _is_likely_match(
    anchor: CensusRecord,
    candidate: CensusRecord,
    birth_year: Optional[int],
) -> bool:
    """Boolean gate — kept for backwards compatibility.

    Uses _names_match (now phonetic-aware) and the same age/sex checks as
    before.  Prefer score_match / best_scored_match for ranked results.
    """
    if not _names_match(anchor.surname, candidate.surname):
        return False
    if anchor.first_name and candidate.first_name:
        if not _names_match(anchor.first_name, candidate.first_name):
            return False

    if birth_year and candidate.birth_year_estimate:
        if abs(candidate.birth_year_estimate - birth_year) > AGE_TOLERANCE:
            return False

    if anchor.sex and candidate.sex:
        if anchor.sex.lower()[0] != candidate.sex.lower()[0]:
            return False

    return True
