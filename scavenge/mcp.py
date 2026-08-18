"""MCP entry point. One tool, no reasoning.

The server acquires evidence and hands it back as structured data. It does not decide
which value is correct, does not generate scraping code, and calls no model. The agent on
the other side does the interpreting — that boundary is the product.

Run with:  python -m scavenge.mcp
"""

from __future__ import annotations

from typing import Any

from mcp.server.mcpserver import MCPServer

from scavenge import robots
from scavenge.acquire import USER_AGENT, rendering_session
from scavenge.engine import FIELDS, UnknownFieldError, inspect_field
from scavenge.safety import UnsafeTargetError, check_target

server = MCPServer("scavenge")

DESCRIPTION = (
    "Inspect a requested field on a webpage across raw HTML, structured metadata, embedded "
    "state, rendered DOM and observed JSON responses. Returns normalized candidate values, "
    "provenance, channel status and deterministic cross-channel relations. It reports "
    "evidence; it does not decide which value is correct."
)


@server.tool(name="inspect_web_field", description=DESCRIPTION)
def inspect_web_field(url: str, field: str = "price") -> dict[str, Any]:
    """Collect field evidence for one URL.

    Args:
        url: the page to inspect; http/https only, public addresses only.
        field: which field to trace. One of: price, availability.
    """
    if field not in FIELDS:
        return _error("unsupported_field", f"field must be one of {sorted(FIELDS)}")

    try:
        check_target(url)
    except UnsafeTargetError as exc:
        return _error("unsafe_target", str(exc))

    decision = robots.fetch(url, USER_AGENT)
    if not decision.allowed:
        return _error("robots_refused", f"{decision.disposition.value} for {url}")

    try:
        with rendering_session() as renderer:
            report = inspect_field(url, field, renderer=renderer)
    except UnsafeTargetError as exc:
        return _error("unsafe_target", str(exc))
    except UnknownFieldError as exc:
        return _error("unsupported_field", str(exc))
    return report.to_dict()


def _error(kind: str, detail: str) -> dict[str, Any]:
    """Errors are returned as data so the agent can act on them, never as a stack trace."""
    return {"error": {"kind": kind, "detail": detail}}


if __name__ == "__main__":
    server.run()
