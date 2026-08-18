"""What the target actually returns, cheaply and then rendered.

Two observations per target: the raw HTTP body, and one browser navigation that also
records the JSON responses the page fetched while loading. Nothing is replayed and
nothing is authenticated; the network record is evidence, not an action.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from time import perf_counter
from typing import Literal

import httpx
from playwright.sync_api import BrowserContext, Response, sync_playwright
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeout

from scavenge.challenge import detect as detect_challenge
from scavenge.models import RenderStatus
from scavenge.safety import check_target

USER_AGENT = "scavenge/0.1 (web-evidence engine; honours robots.txt; one page per run)"
TIMEOUT_SECONDS = 30.0
MAX_JSON_BODY_BYTES = 512 * 1024
MAX_JSON_RESPONSES = 40
LOAD_STATE: Literal["networkidle"] = "networkidle"
# Diagnostic observation does not need a quiescent page — it needs whatever the page has
# after a bounded wait. Many real pages poll forever and never reach networkidle.
SETTLE_MS = 5_000


@dataclass(frozen=True)
class RawObservation:
    url: str
    status: int
    content_type: str
    body: str
    seconds: float


@dataclass(frozen=True)
class NetworkResponse:
    method: str
    url: str
    status: int
    content_type: str
    payload: object | None
    unread_reason: str | None


@dataclass(frozen=True)
class RenderedObservation:
    url: str
    html: str
    responses: tuple[NetworkResponse, ...]
    overflowed: bool
    seconds: float
    status: RenderStatus = RenderStatus.OK
    detail: str = ""


def fetch_raw(url: str, *, allow_private: bool = False) -> RawObservation:
    check_target(url, allow_private=allow_private)
    start = perf_counter()
    with httpx.Client(
        follow_redirects=True,
        timeout=TIMEOUT_SECONDS,
        headers={"User-Agent": USER_AGENT},
    ) as client:
        response = client.get(url)
    return RawObservation(
        url=str(response.url),
        status=response.status_code,
        content_type=response.headers.get("content-type", ""),
        body=response.text,
        seconds=perf_counter() - start,
    )


@dataclass
class _Recorder:
    responses: list[NetworkResponse] = field(default_factory=list)
    overflowed: bool = False

    def on_response(self, response: Response) -> None:
        content_type = response.headers.get("content-type", "")
        if not _looks_like_json(content_type):
            return
        if len(self.responses) >= MAX_JSON_RESPONSES:
            self.overflowed = True
            return
        payload, unread = _read_json(response)
        self.responses.append(
            NetworkResponse(
                method=response.request.method,
                url=response.url,
                status=response.status,
                content_type=content_type.split(";")[0].strip(),
                payload=payload,
                unread_reason=unread,
            )
        )


def _looks_like_json(content_type: str) -> bool:
    lowered = content_type.lower()
    return "json" in lowered


def _read_json(response: Response) -> tuple[object | None, str | None]:
    try:
        body = response.body()
    except Exception as exc:  # noqa: BLE001 - a body can vanish; that is a finding, not a crash
        return None, f"body unavailable: {type(exc).__name__}"
    if len(body) > MAX_JSON_BODY_BYTES:
        return None, f"body {len(body)} bytes exceeds the {MAX_JSON_BODY_BYTES}-byte read cap"
    try:
        return json.loads(body), None
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        return None, f"declared JSON but did not parse: {exc.__class__.__name__}"


@contextmanager
def rendering_session(*, allow_private: bool = False) -> Iterator[Renderer]:
    """One browser for the whole run. Torn down even when a navigation raises."""
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        context = browser.new_context(user_agent=USER_AGENT)
        try:
            yield Renderer(context=context, allow_private=allow_private)
        finally:
            context.close()
            browser.close()


@dataclass
class Renderer:
    context: BrowserContext
    allow_private: bool = False

    def render(self, url: str) -> RenderedObservation:
        """Always returns an observation. Rendering trouble is reported, never raised."""
        check_target(url, allow_private=self.allow_private)
        recorder = _Recorder()
        page = self.context.new_page()
        page.on("response", recorder.on_response)
        start = perf_counter()
        status, detail, html, final_url = RenderStatus.OK, "", "", url
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=int(TIMEOUT_SECONDS * 1000))
            try:
                page.wait_for_load_state(LOAD_STATE, timeout=SETTLE_MS)
            except PlaywrightTimeout:
                # The page never went quiet. Read it anyway and say so.
                status = RenderStatus.PARTIAL_RENDER
                detail = f"no network idle within {SETTLE_MS}ms; read the page as it stood"
            html, final_url = page.content(), page.url
            challenge = detect_challenge(html)
            if challenge is not None:
                status, detail = RenderStatus.BLOCKED_OR_CHALLENGED, challenge
        except PlaywrightTimeout as exc:
            status, detail = RenderStatus.RENDERING_TIMEOUT, _first_line(exc)
        except PlaywrightError as exc:
            status, detail = RenderStatus.RENDERING_FAILED, _first_line(exc)
        finally:
            seconds = perf_counter() - start
            page.close()
        return RenderedObservation(
            url=final_url,
            html=html,
            responses=tuple(recorder.responses),
            overflowed=recorder.overflowed,
            seconds=seconds,
            status=status,
            detail=detail,
        )


def _first_line(exc: Exception) -> str:
    """Playwright errors carry a whole call log; the report wants the one useful line."""
    return str(exc).splitlines()[0].strip()
