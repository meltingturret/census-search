# Prompt: Create a pull request for a feature branch

Use this when a feature branch is ready to merge.

---

I have finished implementing a feature on branch `feature/[name]` in the census-search repository.

Please follow these steps **in order** — do not skip steps 1 or 2:

1. Run `poetry run pytest -v` — **all tests must pass**. Fix any failures before continuing.
2. Run `poetry run ruff check .` — **no lint errors allowed**. Fix any issues before continuing.
3. Review the git diff from main and write a concise commit message if any unstaged changes remain.
4. Push the branch to origin.
5. Run `gh pr create` with a title and body covering:
   - **Summary** — bullet points of what changed
   - **Examples** — `poetry run` commands showing the new behaviour
   - **Test plan** — checklist of tests added/passed
   - Footer: `🤖 Generated with [Claude Code](https://claude.com/claude-code)`

**Branch:** `feature/[name]`
**What this feature does:** [brief description]
