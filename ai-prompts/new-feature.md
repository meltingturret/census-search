# Prompt: Add a new CLI feature

Use this when asking an AI agent to add a new command or flag to census-search.

---

I want to add a new feature to the `census-search` CLI tool.

**Context:**
- Python 3.12, Poetry, Typer, Rich tables, Pydantic v2
- Two searchers: `Census1926Searcher` (Playwright) and `Census1901_1911Searcher` (httpx REST)
- All CLI commands are in `census_search/cli.py`; async work goes in a `_do_*` coroutine
- Tests mock both searchers with `AsyncMock` — no real network calls
- Output is always a Rich `Table` with `box.SIMPLE_HEAD`; no tree output
- Sex filtering is always client-side; dedup key is `(surname, first_name, age, county)` lowercased

**Feature I want:**
[describe the feature here]

**Steps expected:**
1. Create a feature branch: `git checkout -b feature/<name>`
2. Implement the feature in `census_search/cli.py` (and any searcher files if needed)
3. Add tests in `tests/test_cli.py` using `AsyncMock`
4. Update the README.md examples section
5. Run `poetry run pytest -v` and `poetry run ruff check .` — both must pass
6. Commit and push the branch
