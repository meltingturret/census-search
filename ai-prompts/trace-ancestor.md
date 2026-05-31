# Prompt: Trace an ancestor across all three censuses

Use this as a starting point when you want to find someone in 1926, 1911, and 1901.

---

I am researching an Irish ancestor and want to trace them across the 1926, 1911, and 1901 censuses.

**What I know:**
- Surname: [e.g. Corrigan]
- First name: [e.g. James — or variants like "Joe,Joseph" if unsure]
- Approximate birth year: [e.g. 1882 — or omit if unknown]
- County/counties: [e.g. Kilkenny — or "Kilkenny,Tipperary" if unsure]
- Sex: [Male / Female / unknown]

**Suggested commands to try (in order):**

```bash
# 1. Browse without birth year first to see what's there
poetry run census-search link [SURNAME] --county [COUNTY] --sex [SEX]

# 2. Narrow with first name and birth year
poetry run census-search link [SURNAME] --first-name "[FIRST]" \
  --birth-year [YEAR] --county "[COUNTY]" --sex [SEX]

# 3. Widen age window if the person might be older/younger than expected
poetry run census-search link [SURNAME] --first-name "[FIRST]" \
  --birth-year [YEAR] --county "[COUNTY]" --sex [SEX] \
  --age-before 5 --age-after 10

# 4. Show full household and link members to earlier censuses
poetry run census-search link [SURNAME] --first-name "[FIRST]" \
  --birth-year [YEAR] --county "[COUNTY]" --sex [SEX] --expand

# 5. Search 1911 and 1901 directly if no 1926 record exists
poetry run census-search 1911 [SURNAME] --first-name "[FIRST]" --county "[COUNTY]"
poetry run census-search 1901 [SURNAME] --first-name "[FIRST]" --county "[COUNTY]"
```

**Tips:**
- Confidence score ≥ 80% (green) = strong match; 55–79% (yellow) = plausible; < 55% = weak
- Census ages were often approximate — use `--age-before`/`--age-after` for flexibility
- Try multiple counties if the family may have moved: `--county "Kilkenny,Tipperary"`
- Use comma-separated first names for spelling variants: `--first-name "Joe,Joseph,Jos"`
- The Match % column is omitted when there is no birth year (browse mode)
