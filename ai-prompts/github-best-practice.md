# Prompt: GitHub best practice for this repo

Use this to ask an AI agent to review or enforce GitHub hygiene on a branch or PR.

---

I am working on the `census-search` repository at `https://github.com/meltingturret/census-search`.
Please follow these conventions for all Git and GitHub work.

## Branching

- Branch naming: `feature/<short-description>` (e.g. `feature/browse-improvements`)
- Always branch from `main`, never from another feature branch
- One logical change per branch — keep PRs focused

```bash
git checkout main && git pull
git checkout -b feature/<name>
```

## Commits

- Use conventional commit prefixes: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`
- Subject line: imperative mood, under 72 characters
- Body: explain *why*, not *what* — the diff shows what
- Always add co-author line:
  ```
  Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
  ```
- Pass the message via heredoc to preserve formatting:
  ```bash
  git commit -m "$(cat <<'EOF'
  feat: add --max flag to browse command

  Default unchanged at 30. Output now shows total vs displayed count.

  Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
  EOF
  )"
  ```

## Before every PR — mandatory checklist

**Always run both of these before opening or updating a PR. No exceptions.**

```bash
poetry run pytest -v          # all tests must pass — fix failures before pushing
poetry run ruff check .       # no lint errors (line length 120) — fix before pushing
```

Or with make:

```bash
make test && make lint
```

If either command fails, fix the issue and re-run before continuing. Do not open a PR with a failing test suite or lint errors.

## Pull requests

- Title: short imperative phrase matching the commit subject, under 70 chars
- Body must include:
  - **Summary** — bullet points of what changed
  - **Example commands** — showing the new behaviour with `poetry run`
  - **Test plan** — markdown checklist of what was tested
  - Footer: `🤖 Generated with [Claude Code](https://claude.com/claude-code)`
- Keep one feature per PR — avoid bundling unrelated changes
- PR URL pattern: `https://github.com/meltingturret/census-search/pull/new/<branch-name>`

## Example PR body

```markdown
## Summary
- Added `--max` / `-n` flag to the `browse` command (default 30)
- Output now shows `142 record(s) — showing 30` so truncation is visible

## Examples
\`\`\`bash
poetry run census-search browse Corrigan --county Kilkenny --max 100
\`\`\`

## Test plan
- [x] `test_max_passed_to_searcher` — verifies flag is forwarded
- [x] All 180 tests pass

🤖 Generated with [Claude Code](https://claude.com/claude-code)
```

## Merging

- Merge into `main` via GitHub PR — do not push directly to `main`
- Delete the feature branch after merge
- After merge, pull main locally before starting the next branch:
  ```bash
  git checkout main && git pull
  ```
