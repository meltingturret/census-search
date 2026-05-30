"""Base census searcher using Playwright to handle JS-rendered pages."""

from __future__ import annotations

import asyncio
from typing import Any, Optional

from playwright.async_api import Browser, Page, Response, async_playwright


class PlaywrightSearcher:
    """Base class for JS-rendered census searches via Playwright."""

    def __init__(self, headless: bool = True, timeout: int = 30000):
        self.headless = headless
        self.timeout = timeout
        self._browser: Optional[Browser] = None

    async def __aenter__(self):
        self._pw = await async_playwright().start()
        self._browser = await self._pw.chromium.launch(headless=self.headless)
        return self

    async def __aexit__(self, *args):
        if self._browser:
            await self._browser.close()
        await self._pw.stop()

    async def _new_page(self) -> Page:
        context = await self._browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )
        )
        page = await context.new_page()
        page.set_default_timeout(self.timeout)
        return page

    async def _intercept_api_call(
        self,
        page: Page,
        navigate_url: str,
        api_pattern: str,
        wait_selector: str,
    ) -> tuple[Optional[str], Optional[dict]]:
        """
        Navigate to a URL and intercept API calls, returning the one that
        looks like a census records response (not facets/aggregations).
        Returns (api_url, response_json).
        """
        candidates: list[tuple[str, Any]] = []

        async def handle_response(response: Response):
            if api_pattern in response.url:
                try:
                    body = await response.json()
                    candidates.append((response.url, body))
                except Exception:
                    pass

        page.on("response", handle_response)
        await page.goto(navigate_url, wait_until="networkidle")

        for _ in range(20):
            if candidates:
                break
            await asyncio.sleep(0.5)

        # Pick the response that looks like a records payload (not facets/cookies/etc).
        for url, body in candidates:
            if self._looks_like_records(body):
                return url, body

        return None, None

    @staticmethod
    def _looks_like_records(body: Any) -> bool:
        """Return True if body looks like a census records payload."""
        if isinstance(body, dict):
            # Must have a list of record-like objects under a known key.
            for key in ("results", "data", "records", "items"):
                items = body.get(key)
                if isinstance(items, list) and items:
                    first = items[0]
                    if isinstance(first, dict) and "field" not in first:
                        return True
            return False
        if isinstance(body, list):
            if not body:
                return False
            first = body[0]
            # Reject facet payloads: {"field": "...", "counts": [...]}
            if isinstance(first, dict) and "field" in first and "counts" in first:
                return False
            return isinstance(first, dict)
        return False

    async def _get_text(self, page: Page, selector: str, default: str = "") -> str:
        try:
            el = await page.query_selector(selector)
            return (await el.inner_text()).strip() if el else default
        except Exception:
            return default

    async def _get_all_text(self, page: Page, selector: str) -> list[str]:
        try:
            els = await page.query_selector_all(selector)
            return [(await el.inner_text()).strip() for el in els]
        except Exception:
            return []
