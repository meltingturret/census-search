.PHONY: install setup test test-cov lint version release-patch release-minor release-major changelog search search-all link browse help-cli

# One-time setup
install:
	poetry env use python3.12
	poetry install
	poetry run playwright install chromium

# Alias
setup: install

# Run tests
test:
	poetry run pytest -v

# Run tests with coverage summary
test-cov:
	poetry run pytest -v --tb=short -q

# Lint / type check
lint:
	poetry run ruff check .
	poetry run python -m py_compile census_search/cli.py census_search/models.py census_search/linker.py census_search/searchers/*.py
	@echo "Syntax OK"

# ---------------------------------------------------------------------------
# Versioning & release
# ---------------------------------------------------------------------------

# Show current version
version:
	@poetry version

# Bump patch version (0.1.0 → 0.1.1), tag, and push
# Usage: make release-patch
release-patch:
	$(MAKE) _release BUMP=patch

# Bump minor version (0.1.0 → 0.2.0), tag, and push
# Usage: make release-minor
release-minor:
	$(MAKE) _release BUMP=minor

# Bump major version (0.1.0 → 1.0.0), tag, and push
# Usage: make release-major
release-major:
	$(MAKE) _release BUMP=major

# Internal: run tests, bump version, commit, tag, push
_release:
	@echo "Running tests before release..."
	poetry run pytest -q
	poetry run ruff check .
	@echo "Bumping $(BUMP) version..."
	poetry version $(BUMP)
	$(eval NEW_VERSION := $(shell poetry version -s))
	@echo "Updating CHANGELOG.md..."
	@sed -i '' 's/## \[Unreleased\]/## [Unreleased]\n\n---\n\n## [$(NEW_VERSION)] - $(shell date +%Y-%m-%d)/' CHANGELOG.md
	git add pyproject.toml CHANGELOG.md
	git commit -m "chore: release v$(NEW_VERSION)"
	git tag -a "v$(NEW_VERSION)" -m "Release v$(NEW_VERSION)"
	git push && git push --tags
	@echo "Released v$(NEW_VERSION)"

# Open CHANGELOG for editing before a release
changelog:
	$${EDITOR:-vi} CHANGELOG.md

# ---------------------------------------------------------------------------
# Search shortcuts
# ---------------------------------------------------------------------------

# Usage: make search SURNAME=Murphy FIRST=John COUNTY=Dublin YEAR=1911
search:
	poetry run census-search $(if $(YEAR),$(YEAR),1911) $(SURNAME) \
		$(if $(FIRST),--first-name "$(FIRST)",) \
		$(if $(COUNTY),--county "$(COUNTY)",) \
		$(if $(MAX),--max $(MAX),)

# Link by known birth year
# Usage: make link SURNAME=Murphy FIRST=John BIRTH=1880 COUNTY=Kilkenny
link:
	poetry run census-search link $(SURNAME) \
		$(if $(FIRST),--first-name "$(FIRST)",) \
		$(if $(BIRTH),--birth-year $(BIRTH),) \
		$(if $(COUNTY),--county "$(COUNTY)",) \
		$(if $(SEX),--sex "$(SEX)",)

# Browse 1926 by county/surname
# Usage: make browse COUNTY=Dublin  or  make browse SURNAME=Murphy COUNTY=Kilkenny
browse:
	poetry run census-search browse $(SURNAME) \
		$(if $(COUNTY),--county "$(COUNTY)",) \
		$(if $(MAX),--max $(MAX),)

# Show CLI help
help-cli:
	poetry run census-search --help
