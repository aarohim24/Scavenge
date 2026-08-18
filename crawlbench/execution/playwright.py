"""Warm Playwright browser execution for the benchmark's browser arm."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from importlib.metadata import version
from time import perf_counter

from playwright.sync_api import Browser, Page, Response, sync_playwright

from crawlbench.models import Document, ExecutionMode

# Every fixture declares when its rendering is finished by setting this flag. Waiting
# on the fixture's own signal keeps the browser arm deterministic: a fixed sleep would
# either pad every task with idle time or race a slow fixture into a false failure.
READY_FLAG = "window.__CRAWLBENCH_READY === true"
READY_TIMEOUT_MS = 5_000


@dataclass(frozen=True)
class WarmPlaywrightSession:
    browser: Browser
    page: Page
    startup_seconds: float
    playwright_version: str
    chromium_version: str

    def fetch(self, url: str) -> Document:
        response = self.page.goto(url, wait_until="domcontentloaded")
        # A fixture that never signals readiness raises, and the benchmark records the
        # task as FAILED with the timeout's name rather than scoring a half-rendered page.
        self.page.wait_for_function(READY_FLAG, timeout=READY_TIMEOUT_MS)
        html = self.page.content()
        status_code = _response_status(response)
        return Document(
            url=self.page.url,
            status_code=status_code,
            html=html,
            execution_mode=ExecutionMode.PLAYWRIGHT,
            bytes_transferred=None,
        )

    def close(self) -> None:
        self.page.close()
        self.browser.close()


@contextmanager
def launch_warm_playwright_session() -> Iterator[WarmPlaywrightSession]:
    start = perf_counter()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        context = browser.new_context()
        page = context.new_page()
        startup_seconds = perf_counter() - start
        session = WarmPlaywrightSession(
            browser=browser,
            page=page,
            startup_seconds=startup_seconds,
            playwright_version=version("playwright"),
            chromium_version=browser.version,
        )
        try:
            yield session
        finally:
            session.close()


def _response_status(response: Response | None) -> int:
    return 200 if response is None else response.status
