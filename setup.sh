#!/usr/bin/env bash
# One-time setup for census-search

set -e

echo "→ Installing dependencies with Poetry..."
poetry install

echo "→ Installing Playwright browser (Chromium)..."
poetry run playwright install chromium

echo ""
echo "✓ Setup complete. Run searches with:"
echo "  poetry run census-search search Murphy --first-name John --all-years"
echo ""
echo "  If you see a warning about uninstalled scripts, run:"
echo "  poetry install   ← installs the entry point"
echo "  Or use: poetry run python -m census_search search Murphy --first-name John"
