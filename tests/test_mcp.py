"""MCP surface: one tool, errors as data, and the same schema the engine emits."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Iterator

import pytest

from fixtures.scavenge.server import probe_fixture_server
from scavenge import mcp
from scavenge.engine import inspect_field


@pytest.fixture(scope="module")
def base_url() -> Iterator[str]:
    with probe_fixture_server() as url:
        yield url


def test_exactly_one_tool_is_exposed() -> None:
    tools = asyncio.run(mcp.server.list_tools())
    assert [t.name for t in tools] == ["inspect_web_field"]


def test_tool_description_is_factual_not_marketing() -> None:
    tools = asyncio.run(mcp.server.list_tools())
    description = (tools[0].description or "").lower()
    assert "provenance" in description
    assert "does not decide which value is correct" in description
    for banned in ("ai ", "guaranteed", "automatic scraper", "magic"):
        assert banned not in description


def test_unsupported_field_returns_an_error_not_an_exception() -> None:
    result = mcp.inspect_web_field("https://example.com/x", "colour")
    assert result["error"]["kind"] == "unsupported_field"


@pytest.mark.parametrize("url", ["file:///etc/passwd", "http://127.0.0.1/x", "http://10.0.0.1/x"])
def test_unsafe_urls_are_refused_as_data(url: str) -> None:
    result = mcp.inspect_web_field(url, "price")
    assert "error" in result
    assert result["error"]["kind"] in {"unsafe_target", "robots_refused"}


def test_returned_schema_matches_the_engine(base_url: str) -> None:
    """The MCP layer must not reshape the report; it is a transport, not a formatter."""
    direct = inspect_field(
        f"{base_url}/integration", "price", renderer=None, allow_private=True
    ).to_dict()
    assert set(direct) == {
        "schema_version",
        "target",
        "field",
        "observations",
        "acquisition",
        "warnings",
    }
    assert json.dumps(direct)  # serializable as-is, with no MCP-specific coercion
