"""Regression tests for the robots-fetch defect that stalled the commerce redraw.

The redraw sat blocked for 106 minutes on draw #34 because
`RobotFileParser.read()` calls `urlopen()` with no timeout and the server completed its
TLS handshake without ever responding. These tests pin the repaired behaviour: every
failure mode is bounded, named, and never means "allowed".
"""

from __future__ import annotations

import ast
import threading
import time
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest

from scavenge import robots

STALL_SECONDS = 30.0
TEST_TIMEOUT = 0.25
UA = "probe-test"


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler's interface
        mode = self.server.mode  # type: ignore[attr-defined]
        if mode == "stall":
            time.sleep(STALL_SECONDS)
            return
        if mode == "allow":
            body = b"User-agent: *\nAllow: /\n"
        elif mode == "disallow":
            body = b"User-agent: *\nDisallow: /\n"
        elif mode == "oversized":
            body = b"# padding\n" * (robots.MAX_BODY_BYTES // 5)
        elif mode == "unauthorized":
            self.send_error(403)
            return
        elif mode == "server_error":
            self.send_error(503)
            return
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002, ARG002 - stdlib
        """Silent: request logs would bury the test output."""


def _serve(mode: str) -> Iterator[str]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    server.mode = mode  # type: ignore[attr-defined]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/some/page"
    finally:
        server.shutdown()
        server.server_close()


@pytest.fixture
def stalling_url() -> Iterator[str]:
    yield from _serve("stall")


def test_normal_robots_response_allows() -> None:
    for url in _serve("allow"):
        decision = robots.fetch(url, UA)
        assert decision.allowed
        assert decision.disposition is robots.Disposition.ALLOWED


def test_robots_disallow_is_refused() -> None:
    for url in _serve("disallow"):
        decision = robots.fetch(url, UA)
        assert not decision.allowed
        assert decision.disposition is robots.Disposition.DISALLOWED


def test_timeout_is_bounded_named_and_not_permission(stalling_url: str) -> None:
    """The defect in one test: a server that never answers must not block us."""
    start = time.monotonic()
    decision = robots.fetch(stalling_url, UA, timeout=TEST_TIMEOUT)
    elapsed = time.monotonic() - start

    assert decision.disposition is robots.Disposition.ROBOTS_TIMEOUT
    assert not decision.allowed, "a timeout must never be read as permission"
    assert elapsed < STALL_SECONDS / 2, f"did not fail fast: {elapsed:.2f}s"


def test_connection_failure_is_named_and_not_permission() -> None:
    # Port 1 on loopback refuses immediately; no network egress, no waiting.
    decision = robots.fetch("http://127.0.0.1:1/page", UA, timeout=TEST_TIMEOUT)
    assert decision.disposition is robots.Disposition.ROBOTS_UNREACHABLE
    assert not decision.allowed


def test_oversized_robots_is_refused_rather_than_truncated() -> None:
    for url in _serve("oversized"):
        decision = robots.fetch(url, UA)
        assert decision.disposition is robots.Disposition.ROBOTS_OVERSIZED
        assert not decision.allowed


def test_unauthorized_robots_disallows_everything() -> None:
    """Preserves RobotFileParser.read()'s 401/403 semantics."""
    for url in _serve("unauthorized"):
        decision = robots.fetch(url, UA)
        assert not decision.allowed
        assert decision.disposition is robots.Disposition.DISALLOWED


def test_missing_robots_allows_as_the_stdlib_does() -> None:
    for url in _serve("missing"):
        assert robots.fetch(url, UA).allowed


def test_server_error_is_not_read_as_permission() -> None:
    """The stdlib never sets `last_checked` on a 5xx, so `can_fetch` refuses. Same here."""
    for url in _serve("server_error"):
        decision = robots.fetch(url, UA)
        assert not decision.allowed
        assert decision.disposition is robots.Disposition.ROBOTS_UNREACHABLE


def _calls(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            found.add(node.attr)
        elif isinstance(node, ast.Name):
            found.add(node.id)
    return found


PROJECT_NETWORK_PATHS = sorted(Path("scavenge").glob("*.py")) + sorted(
    Path("research").glob("*.py")
)
CALL_SITES = (Path("scavenge/cli.py"), Path("scavenge/mcp.py"), Path("research/select_pdp.py"))


@pytest.mark.parametrize("module", PROJECT_NETWORK_PATHS, ids=lambda p: p.name)
def test_no_unbounded_robots_or_urlopen_remains(module: Path) -> None:
    """No path through the diagnostic or the selector can block forever on robots.txt."""
    names = _calls(module)
    if module.name != "robots.py":
        assert "RobotFileParser" not in names, f"{module} bypasses the bounded fetcher"
    assert "urlopen" not in names, f"{module} uses urlopen, which has no default timeout"


def test_both_call_sites_use_the_shared_fetcher() -> None:
    for path in CALL_SITES:
        assert "robots.fetch(" in path.read_text(), f"{path} does not use the shared fetcher"
