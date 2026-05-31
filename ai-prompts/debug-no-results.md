# Prompt: Debug — person not found

Use this when a search returns no results or the wrong results.

---

I ran a census-search command and got no results (or results that don't look right).

**Command I ran:**
```bash
[paste command here]
```

**Output I got:**
```
[paste output here]
```

**Please help me diagnose the problem by working through these checks:**

1. **Spelling variants** — Try relaxing the surname: omit `--first-name` first, then add it back. Try phonetic variants (e.g. "Brien" for "O'Brien", "Corcoran" for "Cochrane").

2. **Age window** — If using `--birth-year`, try widening with `--age-before 7 --age-after 7`. Census ages were frequently wrong by several years.

3. **County** — The person may have been recorded under a different county boundary. Try neighbouring counties or omit `--county` entirely.

4. **First name variants** — Try comma-separated variants: `--first-name "Mary,Maria,Marie"`. Try just the initial letter or a shortened form.

5. **Sex filter** — Records with no sex recorded are included by default. If using `--sex`, try removing it temporarily.

6. **Year of absence** — If no 1926 record, search 1911 and 1901 directly:
   ```bash
   poetry run census-search 1911 [SURNAME] --county [COUNTY] --max 200
   poetry run census-search 1901 [SURNAME] --county [COUNTY] --max 200
   ```

7. **Increase --max** — The default is 30 results. The person may exist but be past the cutoff:
   ```bash
   poetry run census-search link [SURNAME] --county [COUNTY] --max 200
   ```

8. **Browse the area** — If you know a townland or DED, browse it:
   ```bash
   poetry run census-search browse --county [COUNTY] --ded "[DED]" --max 200
   ```
