# Changelog

All notable changes to this project will be documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Versioning follows [Semantic Versioning](https://semver.org/).

---

## [Unreleased]

---

## [0.7.0] - 2026-06-01

### Added
- `--service-number` flag on `link` command — triggers TNA Discovery API search across WO 372 (WWI medal cards), WO 97 (service records), PIN 82 (widow's pensions), and PIN 26 (disability pension files)
- `WarOfficeSearcher` — two-pass search: WO 372/WO 97 use name + service number; PIN 82/PIN 26 use the regiment extracted from pass 1 to avoid false matches
- Regiment suffix normalisation — strips Depot, Reserve, T.F. etc. before querying pension series
- Rate-limit resilience — 202-empty-body retries with exponential backoff; 1s inter-series delay
- Two output tables: **Military Records** (WO 372/WO 97) and **Dependants & Pensions** (PIN 82/PIN 26)
- `MilitaryRecord` Pydantic model

### Changed
- `--expand` flag removed — household members are always shown and automatically linked to 1911 & 1901
- Household member cross-year tables suppressed when no older census records are found (silent skip)

---

## [0.6.0] - 2026-05-31

### Added
- `census-search 1851`, `1841`, `1831`, `1821` commands — browse surviving pre-Famine census fragments from the National Archives
- `Census1821_1851Searcher` — scrapes the National Archives JSP search page via httpx; no browser required; handles pagination and per-year column layouts
- PyPI publish workflow using OIDC trusted publishing (triggered on GitHub Release)
- `COMMERCIAL_LICENSE.md` — commercial licensing terms for organisations over $1M/year revenue

### Changed
- License changed from Apache 2.0 to Polyform Small Business License 1.0.0
- `pyproject.toml` migrated to PEP 621 `[project]` table (Poetry 2.x)
- README updated with pre-Famine commands, field availability table, and license section

---

## [0.5.0] - 2026-05-31

### Added
- `census-search 1901` and `census-search 1911` commands — browse either census directly without a 1926 anchor
- `CLAUDE.md` — architecture guide for Claude Code
- `AGENTS.md` — constraints and conventions for AI agents
- `ai-prompts/` folder with reusable prompts for tracing ancestors, debugging, feature requests, GitHub workflow

## [0.4.0] - 2026-05-31

### Added
- `browse` command now accepts optional surname positional argument: `census-search browse Corrigan --county Kilkenny`
- `--max` / `-n` flag on `browse` command (default 30); output shows `N record(s) — showing M`

## [0.3.0] - 2026-05-31

### Added
- `--age-before N` / `--age-after N` flags for asymmetric birth-year window
- Multi-variant first name support via comma-separated `--first-name "Joe,Joseph,Jos"`
- Output label shows `±3yr` for symmetric windows, `-5/+10yr` for asymmetric

## [0.2.0] - 2026-05-31

### Added
- Fuzzy/phonetic surname matching (Soundex + difflib) — catches spelling variants like Corrigan/Corigan
- Multi-county search via comma-separated `--county "Kilkenny,Tipperary"`
- Confidence scoring with Match % column (green ≥80%, yellow ≥55%)
- Relationship-aware linking (Son↔Scholar, Daughter↔Scholar etc.)
- `--birth-year` is now optional — omit to browse all 1926 matches as a table
- `--sex` filter enforced client-side; records with no sex field are kept

## [0.1.0] - 2026-05-31

### Added
- Initial release
- `link` command: search 1926, link to 1911 and 1901 by birth year
- Household display as Rich table (auto-shown on single match, `--expand` for all members)
- Birth year label with `±3yr` tolerance indicator
- Primary person excluded from household table
- `browse` command: browse 1926 by county and DED
- `--sex`, `--county`, `--first-name`, `--age-tolerance`, `--max`, `--expand`, `--no-headless` flags
