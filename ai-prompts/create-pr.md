# Prompt: Create a pull request for a feature branch

Use this when a feature branch is ready to merge.

---

I have finished implementing a feature on branch `feature/[name]` in the census-search repository.

Please:
1. Run `poetry run pytest -v` and confirm all tests pass
2. Run `poetry run ruff check .` and fix any lint issues
3. Review the git diff from main and write a concise commit message if any unstaged changes remain
4. Push the branch to origin
5. Provide the GitHub PR URL: `https://github.com/meltingturret/census-search/pull/new/feature/[name]`
6. Suggest a PR title and body covering:
   - What changed (bullet points)
   - Example commands showing the new behaviour
   - Test plan checklist

**Branch:** `feature/[name]`
**What this feature does:** [brief description]
