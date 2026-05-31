# AGENTS.md

Guidance for AI coding agents (Codex, Copilot, etc.) working in this repository.
See CLAUDE.md for the full architecture reference.

## Quick orientation

- **Python 3.12+, Poetry** — all commands prefixed with `poetry run`
- **Two census APIs**: 1926 via Playwright/Chromium (JS-rendered), 1901/1911 via httpx REST
- **All filtering is client-side for 1926** — the API returns broad results; `cli.py` narrows by name/sex/age after fetch
- **Output**: Rich tables only (`box.SIMPLE_HEAD`), no tree output
- **Tests**: `poetry run pytest -v` — no network calls, all searchers are mocked with `AsyncMock`

## Key constraints

- Do not add new runtime dependencies without updating `pyproject.toml` and confirming with the user — the project intentionally has no phonetic/fuzzy deps beyond stdlib `difflib`
- Sex filter must always be applied client-side (API codes differ between 1926 and 1901/1911)
- Deduplication key is always `(surname.lower(), first_name.lower(), age, county.lower())`
- `form_id` (mapped from `aform_name`) is the correct household identifier for 1926 — prefer it over townland matching when available
- Line length limit is **120** (ruff)
- Run `poetry run ruff check .` before committing

## Adding a new CLI command

1. Add `@app.command(name="...")` in `census_search/cli.py`
2. Use `typer.Argument` for positional, `typer.Option` for flags
3. Delegate async work to a `_do_*` coroutine called via `asyncio.run(...)`
4. Mock the searcher in `tests/test_cli.py` with `AsyncMock`
5. Update README.md examples section
