"""Arm A: fetch a page over HTTP, with no browser and no JavaScript execution."""

from __future__ import annotations

import httpx

from crawlbench.models import Document, ExecutionMode

DEFAULT_TIMEOUT_SECONDS = 10.0


def fetch(url: str, *, timeout: float = DEFAULT_TIMEOUT_SECONDS) -> Document:
    """Fetch `url` over HTTP.

    Transport and HTTP-status failures propagate as `httpx` exceptions rather than
    being flattened into an empty `Document`, so the benchmark can tell a fetch
    failure apart from a page that genuinely lacked the data.
    """
    response = httpx.get(url, timeout=timeout, follow_redirects=True)
    response.raise_for_status()
    return Document(
        url=str(response.url),
        status_code=response.status_code,
        html=response.text,
        execution_mode=ExecutionMode.HTTP,
        bytes_transferred=len(response.content),
    )
