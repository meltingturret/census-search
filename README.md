# census-search

CLI tool for tracing individuals across Irish National Archives census records (1926, 1911, 1901, and the pre-Famine fragments 1851, 1841, 1831, 1821).

Searches the **1926 census** by name, then links backwards to **1911** and **1901** using confidence scoring. Results are always displayed as tables. When a single 1926 record is found, the full household is shown automatically.

The **1821–1851 commands** browse the surviving census fragments held by the National Archives. These are partial records — not all counties or returns survived the 1922 Four Courts fire.

## License

Licensed under the [Polyform Small Business License 1.0.0](LICENSE).

- **Free to use** for individuals and organisations with under $1M/year gross revenue.
- **Commercial license required** for organisations with over $1M/year revenue — see [COMMERCIAL_LICENSE.md](COMMERCIAL_LICENSE.md).

## Install

Requires Python 3.12+ and [Poetry](https://python-poetry.org/).

```bash
bash setup.sh
```

Or manually:

```bash
poetry env use python3.12
poetry install
poetry run playwright install chromium
```

## Commands

### `link` — search and link across all three censuses

The primary command. Without `--birth-year`, returns all 1926 matches as a browse table. With `--birth-year`, age-filters results and links each match across 1911 and 1901 with a confidence score.

```bash
# Browse all male Corrigans in Kilkenny (no birth year)
poetry run census-search link Corrigan --county Kilkenny --sex Male

# Link across all three censuses using a known birth year
poetry run census-search link Corrigan --first-name James --birth-year 1882 --county Kilkenny --sex Male

# Search across multiple counties
poetry run census-search link Corrigan --first-name James --birth-year 1882 --county "Kilkenny,Tipperary"

# Search for name variants (Joe, Joseph, Jos) in one pass
poetry run census-search link Corrigan --first-name "Joe,Joseph,Jos" --birth-year 1917 --county Kilkenny --sex Male

# Show household + link all members to 1911 & 1901
poetry run census-search link Corrigan --first-name James --birth-year 1882 --county Kilkenny --expand
```

| Flag | Short | Default | Description |
|------|-------|---------|-------------|
| `--birth-year` | `-b` | | Known or estimated birth year — omit to browse all ages |
| `--first-name` | `-f` | | First name — comma-separate variants (e.g. `Joe,Joseph,Jos`) |
| `--county` | `-c` | | County or comma-separated counties (e.g. `Kilkenny` or `Kilkenny,Tipperary`) |
| `--sex` | `-s` | | `Male` or `Female` — enforced client-side |
| `--expand` | | false | Link all 1926 household members to 1911 & 1901 |
| `--age-tolerance` | | 3 | ±years for age matching across censuses |
| `--max` | `-n` | 30 | Max results per census year |
| `--no-headless` | | | Show browser window (useful for debugging) |

#### Output examples

**Browse without birth year** — returns all matches as a table:

```
$ poetry run census-search link Corrigan --county Kilkenny --sex Male

Corrigan  8 result(s)  add --birth-year to link across 1911 & 1901
 #   Surname    First Name   Age  Sex   County    Townland / Street  DED              Birthplace
 1   Corrigan   James         44  Male  Kilkenny  Lamogue            Kilmaganny
 2   Corrigan   Patrick       52  Male  Kilkenny  Main Street        Kilkenny Urban
 3   Corrigan   Thomas        31  Male  Kilkenny  Ballyline          Scotsborough
 ...
```

**Link with birth year** — one row per census year with a confidence score:

```
$ poetry run census-search link Corrigan --first-name James --birth-year 1882 --county Kilkenny --sex Male

James Corrigan  (born ~1882 ±3yr)
 Year  Surname    First Name   Age  Sex   County    Townland / Street  DED          Birthplace  Match
 1901  Corrigan   James         19  Male  Kilkenny  Lamogue            Kilmaganny                 91%
 1911  Corrigan   James         29  Male  Kilkenny  Lamogue            Kilmaganny                 95%
 1926  Corrigan   James         44  Male  Kilkenny  Lamogue            Kilmaganny                  —

Household  Lamogue, Kilmaganny, Kilkenny
 #   Surname    First Name   Age  Sex     Relationship  County    Townland / Street  DED
 1   Corrigan   Mary          39  Female  Wife          Kilkenny  Lamogue            Kilmaganny
 2   Corrigan   Brigid        14  Female  Daughter      Kilkenny  Lamogue            Kilmaganny
 3   Corrigan   Patrick        9  Male    Son           Kilkenny  Lamogue            Kilmaganny
```

**Multiple first name variants** — searches all variants and shows whichever name appears in the record:

```
$ poetry run census-search link Corrigan --first-name "Joe,Joseph,Jos" \
    --birth-year 1917 --county "Kilkenny,Tipperary" --sex Male

Joe / Joseph / Jos Corrigan  (born ~1917 ±3yr)
 Year  Surname    First Name   Age  Sex   County    Townland / Street  DED          Birthplace  Match
 1901  Corrigan   Joseph         0  Male  Kilkenny  Lamogue            Kilmaganny                 78%
 1911  Corrigan   Joe            6  Male  Kilkenny  Lamogue            Kilmaganny                 82%
 1926  Corrigan   Joseph         9  Male  Kilkenny  Lamogue            Kilmaganny                  —
```

**Multi-county search** — merges results from both counties:

```
$ poetry run census-search link Purcell --first-name Mary --birth-year 1887 --county "Kilkenny,Tipperary" --sex Female

Mary Purcell  (born ~1887 ±3yr)
 Year  Surname  First Name  Age  Sex     County    Townland / Street  DED                 Birthplace  Match
 1901  Purcell  Mary         14  Female  Kilkenny  Ballyline          Scotsborough                      92%
 1911  Purcell  Mary         22  Female  Kilkenny  Brownstown         Kilkenny Rural                    88%
 1926  Purcell  Mary         38  Female  Kilkenny  Balief Upper       Clomantagh                         —
```

**Expand household** — links each member back to 1911 & 1901:

```
$ poetry run census-search link Corrigan --first-name James --birth-year 1882 --county Kilkenny --expand

James Corrigan  (born ~1882 ±3yr)
 Year  Surname   First Name  Age  Sex   County    Townland / Street  DED          Birthplace  Match
 1901  Corrigan  James        19  Male  Kilkenny  Lamogue            Kilmaganny                 91%
 1911  Corrigan  James        29  Male  Kilkenny  Lamogue            Kilmaganny                 95%
 1926  Corrigan  James        44  Male  Kilkenny  Lamogue            Kilmaganny                  —

Household  Lamogue, Kilmaganny, Kilkenny
 #  Surname   First Name  Age  Sex     Relationship  County    Townland / Street  DED          Birthplace
 1  Corrigan  Mary         39  Female  Wife          Kilkenny  Lamogue            Kilmaganny
 2  Corrigan  Brigid       14  Female  Daughter      Kilkenny  Lamogue            Kilmaganny
 3  Corrigan  Patrick       9  Male    Son           Kilkenny  Lamogue            Kilmaganny

Mary Corrigan  (born ~1887 ±3yr)
 Year  Surname   First Name  Age  Sex     County    Townland / Street  DED          Birthplace  Match
 1911  Corrigan  Mary         24  Female  Kilkenny  Lamogue            Kilmaganny                 87%
 1901  Corrigan  Mary         14  Female  Kilkenny  Lamogue            Kilmaganny                 79%

Patrick Corrigan  (born ~1917 ±3yr)
 Year  Surname   First Name  Age  Sex   County    Townland / Street  DED          Birthplace  Match
 1926  Corrigan  Patrick       9  Male  Kilkenny  Lamogue            Kilmaganny                  —
```

When a household is found it is shown below as a separate table. `--expand` adds a further per-member cross-year table for each household member born before 1926.

#### How `--expand` handles absent persons

If the target person is not in 1926 (e.g. away on military service), the first surname match in the area is used as the household address anchor. Family members listed at that address are fetched and linked backwards.

---

### `browse` — browse by county/DED (no name required)

```bash
# Browse all records in a county
poetry run census-search browse --county Dublin

# Browse a specific DED
poetry run census-search browse --county Kerry --ded "Tralee Urban"

# Filter by surname within a county
poetry run census-search browse Corrigan --county Kilkenny

# Increase result limit
poetry run census-search browse Corrigan --county Kilkenny --max 100
```

| Argument / Flag | Short | Default | Description |
|-----------------|-------|---------|-------------|
| `surname` | | | Surname to filter by (optional positional argument) |
| `--county` | `-c` | | County to browse |
| `--ded` | `-d` | | District Electoral Division |
| `--max` | `-n` | 30 | Max results to return |

---

### `1901` / `1911` — browse those censuses directly (no 1926 anchor needed)

```bash
# Browse all Corrigans in Tipperary in 1901
poetry run census-search 1901 Corrigan --county Tipperary --max 300

# Browse all Corrigans in Tipperary in 1911
poetry run census-search 1911 Corrigan --county Tipperary --max 300

# Filter by first name and sex
poetry run census-search 1911 Corrigan --first-name James --county Kilkenny --sex Male

# Multiple name variants, multiple counties
poetry run census-search 1901 Murphy --first-name "Mary,Maria" --county "Kilkenny,Tipperary"
```

| Argument / Flag | Short | Default | Description |
|-----------------|-------|---------|-------------|
| `surname` | | | Surname to search (optional positional argument) |
| `--first-name` | `-f` | | First name — comma-separate variants (e.g. `Joe,Joseph`) |
| `--county` | `-c` | | County or comma-separated counties |
| `--sex` | `-s` | | `Male` or `Female` — enforced client-side |
| `--max` | `-n` | 30 | Max results to return |

#### Output example

```
$ poetry run census-search 1911 Corrigan --county Tipperary --max 300

📂 Browsing 1911 census — Corrigan

142 record(s) — showing 142
 #   Surname    First Name   Age  Sex   County     Townland / Street  DED          Birthplace
 1   Corrigan   James         29  Male  Tipperary  Main Street        Clonmel
 2   Corrigan   Mary          24  Female Tipperary Barrack Street     Clonmel
 ...
```

---

### `1851` / `1841` / `1831` / `1821` — pre-Famine census fragments

Browse the surviving pre-Famine census returns held by the National Archives. These are partial records — coverage varies by county and year due to destruction in the 1922 Four Courts fire.

```bash
# 1851 — full personal detail (age, sex, relation, occupation, birthplace)
poetry run census-search 1851 Murphy --county Antrim

# 1841 — same columns as 1851
poetry run census-search 1841 Corrigan --county Kilkenny --sex Female

# 1831 — household-level stats (no individual age/sex)
poetry run census-search 1831 Corrigan

# 1821 — includes age, occupation, relation to head
poetry run census-search 1821 Murphy --county Meath
```

| Argument / Flag | Short | Default | Description |
|-----------------|-------|---------|-------------|
| `surname` | | | Surname to search (optional positional argument) |
| `--first-name` | `-f` | | First name |
| `--county` | `-c` | | County |
| `--sex` | `-s` | | `Male` or `Female` — 1841/1851 only (those years have individual sex records) |
| `--max` | `-n` | 30 | Max results to return |

**Available fields by year:**

| Year | Age | Sex | Relation | Occupation | Birthplace | Notes |
|------|-----|-----|----------|------------|------------|-------|
| 1851 | ✓ | ✓ | ✓ | ✓ | ✓ | Most complete fragment |
| 1841 | ✓ | ✓ | ✓ | ✓ | ✓ | |
| 1831 | — | — | — | — | — | Household aggregate stats only |
| 1821 | ✓ | — | ✓ | ✓ | — | Individual records, no sex column |

---

## How it works

1. **Search 1926**: Playwright opens a Chromium browser, intercepts the underlying API call, and extracts structured results. Filtering by first name, sex, and age is done client-side.
2. **Household**: When a single 1926 record is matched, all household members on the same PDF form (`aform_name`) are fetched automatically.
3. **Search 1911 & 1901**: Uses a direct REST API — no browser required. Results are filtered by surname, age window (`expected_age ± tolerance`), and county. Multiple counties can be searched and merged.
4. **Phonetic matching**: Surname variants are caught using Soundex (e.g. Corrigan/Corigan, Purcell/Pursell) and fuzzy string similarity.
5. **Confidence scoring**: Each candidate is scored across surname, first name, age consistency, county, sex, and relationship. The best match above the threshold is shown with a percentage.
6. **Relationship-aware linking**: Relationship compatibility across years is factored into scoring (e.g. Son↔Scholar, Daughter↔Scholar score higher than unrelated pairs).

## Notes

- The 1926 census site is JavaScript-rendered. Playwright/Chromium is required. On first run, Playwright downloads Chromium (~150 MB).
- The 1901/1911 search uses a direct REST API — no browser needed for that step.
- The 1821–1851 commands scrape the National Archives search page (plain HTML, no browser required). Coverage is sparse — many returns did not survive.
- Age tolerance of ±3 years is the default — census ages were often approximate.
- `--expand` links all household members who have a recorded age.
- Census ages are not always accurate; the confidence score reflects how well each linked record fits across all available fields.
