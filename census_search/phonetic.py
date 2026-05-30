"""Phonetic name-matching utilities.

Uses Soundex (for Irish surname variants) and difflib SequenceMatcher
(for general fuzzy similarity). No third-party dependencies required.
"""

from __future__ import annotations

import difflib
import re

# Soundex digit map — covers all consonants relevant to Irish names
_SOUNDEX_MAP: dict[str, str] = {
    c: d
    for d, chars in [
        ("1", "BFPV"),
        ("2", "CGJKQSXZ"),
        ("3", "DT"),
        ("4", "L"),
        ("5", "MN"),
        ("6", "R"),
    ]
    for c in chars
}


def soundex(name: str) -> str:
    """Return a 4-character Soundex code for *name*.

    Examples
    --------
    >>> soundex("Corrigan")
    'C625'
    >>> soundex("Corigan")
    'C625'
    >>> soundex("Purcell")
    'P624'
    >>> soundex("Pursell")
    'P624'
    """
    name = re.sub(r"[^A-Za-z]", "", name).upper()
    if not name:
        return "0000"

    first = name[0]
    prev_digit = _SOUNDEX_MAP.get(first, "0")
    code = first

    for ch in name[1:]:
        if ch in "HW":  # ignored but don't reset prev_digit
            continue
        digit = _SOUNDEX_MAP.get(ch, "0")
        if digit != "0" and digit != prev_digit:
            code += digit
            if len(code) == 4:
                break
        prev_digit = digit

    return code.ljust(4, "0")


def name_similarity(a: str, b: str) -> float:
    """Return a 0.0–1.0 similarity ratio between two name strings.

    Uses difflib SequenceMatcher which handles transpositions and minor
    spelling differences well (e.g. "Mary" / "Marie" → ~0.89).
    """
    a, b = a.strip().lower(), b.strip().lower()
    if not a or not b:
        return 0.0
    return difflib.SequenceMatcher(None, a, b).ratio()
