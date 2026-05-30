.PHONY: install setup test lint search browse link

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

# Lint / type check (optional, install ruff/mypy if wanted)
lint:
	poetry run python -m py_compile census_search/cli.py census_search/models.py census_search/linker.py census_search/searchers/*.py
	@echo "Syntax OK"

# --- Search shortcuts ---

# Usage: make search SURNAME=Murphy FIRST=John COUNTY=Dublin
search:
	poetry run census-search search $(SURNAME) \
		$(if $(FIRST),--first-name "$(FIRST)",) \
		$(if $(COUNTY),--county "$(COUNTY)",) \
		$(if $(EXACT),--exact,) \
		$(if $(ALL),--all-years,)

# Recursive search across 1926 → 1911 → 1901
# Usage: make search-all SURNAME=Murphy FIRST=John
search-all:
	poetry run census-search search $(SURNAME) \
		$(if $(FIRST),--first-name "$(FIRST)",) \
		$(if $(COUNTY),--county "$(COUNTY)",) \
		--all-years

# Link by known birth year
# Usage: make link SURNAME=Murphy FIRST=John BIRTH=1880
link:
	poetry run census-search link $(SURNAME) \
		$(if $(FIRST),--first-name "$(FIRST)",) \
		--birth-year $(BIRTH) \
		$(if $(COUNTY),--county "$(COUNTY)",)

# Browse by county
# Usage: make browse COUNTY=Dublin
browse:
	poetry run census-search browse \
		$(if $(COUNTY),--county "$(COUNTY)",)

# Show CLI help
help-cli:
	poetry run census-search --help
