# census-search

CLI tool for tracing individuals across Irish National Archives census records (1926, 1911, 1901).

Searches the **1926 census** by name and birth year, links forward to **1911** and **1901**, and can expand to the full household — useful when the primary person is absent (e.g. away on military service) but family members are listed at the address.

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

### `link` — search all three censuses for a person

The primary command. Searches 1926, 1911, and 1901 simultaneously using a known birth year.

When exactly one 1926 record is found, the full household is shown automatically. Use `--expand` to also link each household member back to 1911 and 1901.

```bash
# Basic search
poetry run census-search link Corrigan --first-name James --birth-year 1882 --county Kilkenny --sex Male

# Show household + link all members to 1911 & 1901
poetry run census-search link Corrigan --first-name James --birth-year 1882 --county Kilkenny --expand
```

| Flag | Short | Default | Description |
|------|-------|---------|-------------|
| `--birth-year` | `-b` | required | Known or estimated birth year |
| `--first-name` | `-f` | | First name |
| `--county` | `-c` | | County (e.g. `Kilkenny`, `Dublin`) |
| `--sex` | `-s` | | `Male` or `Female` |
| `--expand` | | false | Link all 1926 household members to 1911 & 1901 |
| `--age-tolerance` | | 3 | ±years for age matching across censuses |
| `--max` | `-n` | 30 | Max results per census year |
| `--no-headless` | | | Show browser window (useful for debugging) |

#### How `--expand` handles absent persons

If the target person is not found in 1926 (e.g. away on military service), the first surname match in the county is used as the household address anchor. The wife or other family members listed at that address are then fetched and linked backwards.

---

### `browse` — browse by county/DED (no name required)

```bash
poetry run census-search browse --county Dublin
poetry run census-search browse --county Kerry --ded "Tralee Urban"
```

| Flag | Short | Description |
|------|-------|-------------|
| `--county` | `-c` | County to browse |
| `--ded` | `-d` | District Electoral Division |

---

## How it works

1. **Search 1926**: Playwright opens a Chromium browser, intercepts the underlying API call, and extracts structured results. The 1926 API does not support first-name filtering server-side — name and age filtering is done client-side.
2. **Household**: When a single 1926 record is matched, all household members sharing the same form are fetched automatically (identified by the `aform_name` PDF form ID).
3. **Search 1911 & 1901**: Uses a direct REST API — no browser required. Results are filtered by surname, age window (`expected_age ± tolerance`), and optionally sex and county.
4. **Linking**: Records are matched across years using name similarity, age consistency, sex, and county.

## Notes

- The 1926 census site is JavaScript-rendered. Playwright/Chromium is required. On first run, Playwright downloads Chromium (~150 MB).
- The 1901/1911 search uses a direct REST API — no browser needed for that step.
- Age tolerance of 3 years is recommended — census ages were often approximate.
- `--expand` links up to all members of the household who have a recorded age.
