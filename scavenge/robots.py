"""Bounded robots.txt fetching, shared by target selection and `probe inspect`.

`urllib.robotparser.RobotFileParser.read()` calls `urllib.request.urlopen()` with no
timeout, so a server that completes a TLS handshake and then never responds blocks the
caller forever. That is not hypothetical: it stalled the commerce redraw for 106 minutes
on draw #34 (see docs/research/PROBE-PROTOCOL.md §14).

So we fetch the body ourselves, with an explicit timeout and an explicit size cap, and
hand the text to `RobotFileParser.parse()` — keeping stdlib robots semantics while
bounding the network. Every failure produces a named disposition; none of them means
"allowed".
"""

from __future__ import annotations

import urllib.robotparser
from dataclasses import dataclass
from enum import StrEnum
from urllib.parse import urlparse

import httpx

TIMEOUT_SECONDS = 10.0
MAX_BODY_BYTES = 500 * 1024  # Google's documented robots.txt parse limit.
_UNAUTHORIZED = (401, 403)
_HTTP_OK = 200
_CLIENT_ERROR_FLOOR = 400
_SERVER_ERROR_FLOOR = 500


class Disposition(StrEnum):
    ALLOWED = "ALLOWED"
    DISALLOWED = "DISALLOWED"
    ROBOTS_TIMEOUT = "ROBOTS_TIMEOUT"
    ROBOTS_UNREACHABLE = "ROBOTS_UNREACHABLE"
    ROBOTS_OVERSIZED = "ROBOTS_OVERSIZED"


@dataclass(frozen=True)
class Decision:
    allowed: bool
    disposition: Disposition


def _robots_url(url: str) -> str:
    parts = urlparse(url)
    return f"{parts.scheme}://{parts.netloc}/robots.txt"


def fetch(url: str, user_agent: str, *, timeout: float = TIMEOUT_SECONDS) -> Decision:
    """Whether `user_agent` may fetch `url`, with a named reason when we could not tell.

    `timeout` is a parameter so the regression test can fail in a fraction of a second
    instead of waiting out the production value.
    """
    try:
        status, body = _read_body(_robots_url(url), user_agent, timeout=timeout)
    except httpx.TimeoutException:
        return Decision(False, Disposition.ROBOTS_TIMEOUT)
    except _OversizedError:
        return Decision(False, Disposition.ROBOTS_OVERSIZED)
    except httpx.HTTPError:
        return Decision(False, Disposition.ROBOTS_UNREACHABLE)

    return _decide(status, body, url, user_agent)


def _decide(status: int, body: str | None, url: str, user_agent: str) -> Decision:
    """Reproduces `RobotFileParser.read()`'s status semantics, spelled out.

    401/403 disallow everything; any other 4xx allows everything; 2xx is parsed. For any
    other status the stdlib never sets `last_checked`, and `can_fetch` then refuses — so
    a 5xx is a refusal, not permission. Writing these out is what caught the divergence:
    an empty parser refuses a missing robots.txt, where the stdlib allows it.
    """
    if status in _UNAUTHORIZED:
        return Decision(False, Disposition.DISALLOWED)
    if _CLIENT_ERROR_FLOOR <= status < _SERVER_ERROR_FLOOR:
        return Decision(True, Disposition.ALLOWED)
    if status != _HTTP_OK or body is None:
        return Decision(False, Disposition.ROBOTS_UNREACHABLE)

    parser = urllib.robotparser.RobotFileParser()
    parser.parse(body.splitlines())
    allowed = parser.can_fetch(user_agent, url)
    return Decision(allowed, Disposition.ALLOWED if allowed else Disposition.DISALLOWED)


class _OversizedError(Exception):
    """A robots.txt past the size cap is refused rather than truncated and misparsed."""


def _read_body(robots_url: str, user_agent: str, *, timeout: float) -> tuple[int, str | None]:
    """The status, and the body text when there is one worth parsing."""
    with (
        httpx.Client(
            follow_redirects=True, timeout=timeout, headers={"User-Agent": user_agent}
        ) as client,
        client.stream("GET", robots_url) as response,
    ):
        if response.status_code != _HTTP_OK:
            return response.status_code, None
        chunks: list[bytes] = []
        total = 0
        for chunk in response.iter_bytes():
            total += len(chunk)
            if total > MAX_BODY_BYTES:
                raise _OversizedError(robots_url)
            chunks.append(chunk)
    return _HTTP_OK, b"".join(chunks).decode("utf-8", errors="replace")
