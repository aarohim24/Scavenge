"""The CLI is a shell over the engine and must not diverge from it."""

from __future__ import annotations

import json
from collections.abc import Iterator

import pytest

from fixtures.scavenge.server import probe_fixture_server
from scavenge import cli, robots
from scavenge.cli import main
from scavenge.engine import inspect_field
from scavenge.robots import Decision, Disposition

_ALLOWED = Decision(True, Disposition.ALLOWED)


@pytest.fixture(scope="module")
def base_url() -> Iterator[str]:
    with probe_fixture_server() as url:
        yield url


def test_cli_json_is_exactly_the_engine_report(
    base_url: str, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The CLI prints the engine's report verbatim; it must not reshape or summarise it."""
    url = f"{base_url}/integration"
    report = inspect_field(url, "price", renderer=None, allow_private=True)
    monkeypatch.setattr(cli, "inspect_field", lambda *_a, **_k: report)
    monkeypatch.setattr(robots, "fetch", lambda *_a, **_k: _ALLOWED)
    monkeypatch.setattr(cli, "check_target", lambda *_a, **_k: None)

    assert main(["inspect", url, "--field", "price", "--json", "--no-render"]) == 0
    assert json.loads(capsys.readouterr().out) == report.to_dict()


def test_cli_names_the_real_reason_for_an_unsafe_scheme(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A file:// URL is refused because the scheme is not fetchable, not because its
    robots.txt could not be read. The target is validated before anything is requested."""
    assert main(["inspect", "file:///etc/passwd", "--field", "price"]) == cli.EXIT_REFUSED
    error = capsys.readouterr().err
    assert "not fetchable" in error
    assert "ROBOTS" not in error


def test_cli_refuses_a_private_target(base_url: str, capsys: pytest.CaptureFixture[str]) -> None:
    """Loopback is refused through the real code path, with no test seam to bypass it."""
    exit_code = main(["inspect", f"{base_url}/integration", "--field", "price", "--no-render"])
    assert exit_code == cli.EXIT_REFUSED
    assert "refusing" in capsys.readouterr().err


def test_cli_rejects_an_unsupported_field(base_url: str) -> None:
    with pytest.raises(SystemExit):
        main(["inspect", f"{base_url}/integration", "--field", "colour", "--no-render"])
