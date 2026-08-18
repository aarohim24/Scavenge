"""Polite collection: robots, pacing, and backoff.

The invalid pilot sent requests at a fixed 1 s interval and ignored the 429s it got
back, so 42% of its responses were throttle pages. This module treats throttling as a
signal to slow down and, past a bounded number of retries, to mark the domain
unavailable rather than to work around it.
"""

from __future__ import annotations

import gzip
import time
import urllib.robotparser
from dataclasses import dataclass, field
from urllib.parse import urlparse

import httpx

USER_AGENT = "CrawlBenchResearch/0.1 (methodology pilot; honours robots.txt; low rate)"
MIN_INTERVAL_SECONDS = 2.0
MAX_RETRIES = 3
BACKOFF_BASE_SECONDS = 5.0
MAX_BACKOFF_SECONDS = 60.0
HTTP_OK = 200
HTTP_TOO_MANY = 429
RETRYABLE = frozenset({429, 502, 503, 504})


@dataclass(frozen=True)
class FetchOutcome:
    url: str
    status: int | None
    body: str | None
    error: str | None
    attempts: int
    throttled: bool
    waited_seconds: float

    @property
    def ok(self) -> bool:
        return self.status == HTTP_OK and self.body is not None


@dataclass
class PoliteFetcher:
    """Per-domain pacing with exponential backoff. No proxies, no evasion."""

    min_interval: float = MIN_INTERVAL_SECONDS
    max_retries: int = MAX_RETRIES
    _last_request: dict[str, float] = field(default_factory=dict)
    _penalty: dict[str, float] = field(default_factory=dict)
    throttle_log: list[tuple[str, str, float]] = field(default_factory=list)
    unavailable: dict[str, str] = field(default_factory=dict)

    def _wait_for(self, domain: str) -> float:
        interval = self.min_interval + self._penalty.get(domain, 0.0)
        elapsed = time.monotonic() - self._last_request.get(domain, 0.0)
        delay = max(0.0, interval - elapsed)
        if delay:
            time.sleep(delay)
        self._last_request[domain] = time.monotonic()
        return delay

    def get(self, url: str, *, timeout: float = 25.0) -> FetchOutcome:
        domain = urlparse(url).netloc
        if domain in self.unavailable:
            return FetchOutcome(url, None, None, self.unavailable[domain], 0, False, 0.0)

        waited = 0.0
        throttled = False
        for attempt in range(1, self.max_retries + 1):
            waited += self._wait_for(domain)
            try:
                response = httpx.get(
                    url,
                    timeout=timeout,
                    follow_redirects=True,
                    headers={"User-Agent": USER_AGENT},
                )
            except httpx.HTTPError as exc:
                if attempt == self.max_retries:
                    return FetchOutcome(
                        url, None, None, type(exc).__name__, attempt, throttled, waited
                    )
                continue

            if response.status_code not in RETRYABLE:
                body = None
                if response.status_code == HTTP_OK:
                    # Sitemaps are routinely gzipped; the invalid pilot read them as text.
                    raw = response.content
                    if url.endswith(".gz") or raw[:2] == b"\x1f\x8b":
                        try:
                            body = gzip.decompress(raw).decode("utf-8", "replace")
                        except OSError:
                            body = None
                    else:
                        body = response.text
                return FetchOutcome(
                    url, response.status_code, body, None, attempt, throttled, waited
                )

            throttled = True
            pause = self._backoff_for(response, attempt)
            self.throttle_log.append((domain, f"HTTP {response.status_code}", pause))
            # Slow every later request to this domain, not just the retry.
            self._penalty[domain] = min(
                MAX_BACKOFF_SECONDS, self._penalty.get(domain, 0.0) + self.min_interval
            )
            time.sleep(pause)
            waited += pause

        self.unavailable[domain] = "throttled_beyond_retry_budget"
        return FetchOutcome(
            url, HTTP_TOO_MANY, None, self.unavailable[domain], self.max_retries, True, waited
        )

    def _backoff_for(self, response: httpx.Response, attempt: int) -> float:
        """Honour Retry-After when the server supplies it; otherwise exponential."""
        header = response.headers.get("Retry-After")
        if header:
            try:
                return min(MAX_BACKOFF_SECONDS, float(header))
            except ValueError:
                pass
        return min(MAX_BACKOFF_SECONDS, BACKOFF_BASE_SECONDS * (2 ** (attempt - 1)))


def robots_for(domain: str, fetcher: PoliteFetcher) -> urllib.robotparser.RobotFileParser | None:
    outcome = fetcher.get(f"https://{domain}/robots.txt", timeout=15)
    if not outcome.ok or outcome.body is None:
        return None
    parser = urllib.robotparser.RobotFileParser()
    parser.set_url(f"https://{domain}/robots.txt")
    parser.parse(outcome.body.splitlines())
    return parser
