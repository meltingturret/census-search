# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Setup (one-time)
poetry env use python3.12
poetry install
poetry run playwright install chromium

# Run all tests
poetry run pytest -v

# Run a single test
poetry run pytest tests/test_cli.py::TestLinkCommand::test_exits_0_with_results -v

# Lint (syntax check)
poetry run python -m py_compile census_search/cli.py census_search/models.py census_search/linker.py census_search/searchers/*.py

# Ruff (style/import checks — line length 120)
poetry run ruff check .

# Run the CLI
poetry run census-search --help
poetry run census-search link Corrigan --first-name James --county Kilkenny --birth-year 1882
poetry run census-search 1911 Corrigan --county Kilkenny --max 100
poetry run census-search browse Corrigan --county Kilkenny
```

## Architecture

### Data flow

```
CLI command (cli.py)
  └─ Census1926Searcher        — Playwright/Chromium, intercepts API calls on nationalarchives.ie
  └─ Census1901_1911Searcher   — httpx async REST calls to api-census.nationalarchives.ie
       └─ linker.py            — score_match / best_scored_match picks best cross-year candidate
            └─ phonetic.py     — Soundex + difflib similarity for fuzzy name matching
```

### Two distinct searcher strategies

**1926 (`searchers/census_1926.py`)** — JS-rendered site, no public API. `PlaywrightSearcher` (base class in `searchers/base.py`) launches Chromium, navigates to the search page, and intercepts the underlying network API call via `page.on("response", ...)`. All filtering by first name, sex, and age is done **client-side after fetch** because the 1926 API does not reliably support these parameters.

**1901/1911 (`searchers/census_1901_1911.py`)** — REST API at `api-census.nationalarchives.ie/census/query`. Uses httpx. Supports server-side filters (`surname__icontains`, `age__gte`, etc.). `search_both_years()` fans out across multiple counties and/or first-name variants and deduplicates by `(surname, first_name, age, county)`.

### Models (`models.py`)

Three Pydantic v2 models:
- `CensusRecord` — one person row; `form_id` (field `aform_name`) identifies the 1926 household PDF; `birth_year_estimate` is a computed property.
- `SearchResult` — wraps a list of records with `total` and `search_url`.
- `LinkedPerson` — a person found across multiple years (used internally by `linker.py`).

### Confidence scoring (`linker.py`)

`score_match(anchor, candidate)` returns 0–1 using weighted fields:

| Field        | Weight |
|--------------|--------|
| Surname      | 3      |
| First name   | 2      |
| Age (birth year consistency) | 3 |
| County       | 1      |
| Sex          | 1      |
| Relationship | 1      |

`_name_score()` gives partial credit: exact → prefix → Soundex → difflib similarity. `MATCH_THRESHOLD = 0.40` gates what counts as a real match. Relationship compatibility (e.g. Son↔Scholar) is in `_REL_COMPAT`.

### CLI commands (`cli.py`)

| Command   | Source          | Notes |
|-----------|-----------------|-------|
| `link`    | 1926 + 1901/1911 | Primary command; `--birth-year` optional; `--expand` links household |
| `browse`  | 1926 only        | Optional surname positional arg |
| `1901`    | 1901 only        | Direct REST browse |
| `1911`    | 1911 only        | Direct REST browse |

All output uses Rich `Table` with `box.SIMPLE_HEAD`. No Tree output anywhere. Sex filtering is always done client-side. Multi-county and multi-first-name support uses comma-separated values; results are deduplicated before display.

### Asymmetric age tolerance

`--age-before` (person may be older) and `--age-after` (person may be younger) override `--age-tolerance` on either end. Passed through from `cli.py` → `_do_link` → `Census1901_1911Searcher.search_both_years()` as `tol_before` / `tol_after`.

### Testing

Tests are in `tests/` and use `unittest.mock.AsyncMock` to patch `Census1926Searcher` and `Census1901_1911Searcher`. No real network calls in tests. `pytest-asyncio` with `asyncio_mode = "auto"` (set in `pyproject.toml`). The Typer `CliRunner` has a narrow terminal — Rich truncates rightmost columns, so test assertions use mid-table values (e.g. ages) rather than the rightmost Match column.
