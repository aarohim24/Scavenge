"""The deterministic case corpus, carried over from the prototype and re-expressed.

Every logical case the prototype covered is still covered here; the assertions moved from
"what did it recommend" to "what did it observe", because the recommendation layer was
removed. The repair cases from the retest are included unchanged in substance.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest

from fixtures.scavenge.server import probe_fixture_server
from scavenge.acquire import (
    RenderedObservation,
    Renderer,
    fetch_raw,
    rendering_session,
)
from scavenge.engine import inspect_field
from scavenge.models import (
    Channel,
    EvidenceReport,
    MoneyValue,
    Observation,
    RenderStatus,
)
from scavenge.money import Money as MoneyType
from scavenge.price import _parse as _money
from scavenge.price import from_dom
from scavenge.render import render
from scavenge.safety import UnsafeTargetError, check_target

# Priced pages in realworld/preflight/manifest.json; guards against a silent no-op loop.
PREFLIGHT_PRICED_PAGES = 10


@pytest.fixture(scope="module")
def base_url() -> Iterator[str]:
    with probe_fixture_server() as url:
        yield url


@pytest.fixture(scope="module")
def renderer() -> Iterator[Renderer]:
    with rendering_session(allow_private=True) as active:
        yield active


def inspect(base_url: str, renderer: Renderer | None, path: str) -> EvidenceReport:
    return inspect_field(f"{base_url}{path}", "price", renderer=renderer, allow_private=True)


def amount_of(observation: Observation) -> str:
    """Narrow the value union in one place instead of at every assertion."""
    value = observation.normalized_value
    assert isinstance(value, MoneyValue)
    return str(value.amount)


def valued(report: EvidenceReport, channel: Channel) -> list[Observation]:
    return [
        o for o in report.observations if o.channel is channel and o.normalized_value is not None
    ]


def value_of(report: EvidenceReport, channel: Channel) -> str | None:
    found = valued(report, channel)
    return str(found[0].normalized_value) if found else None


def test_value_present_in_raw_and_unchanged_by_rendering(base_url: str, renderer: Renderer) -> None:
    report = inspect(base_url, renderer, "/http-sufficient")
    assert valued(report, Channel.RAW_DOM)
    assert value_of(report, Channel.RAW_DOM) == value_of(report, Channel.RENDERED_DOM)


def test_rendering_changes_the_value(base_url: str, renderer: Renderer) -> None:
    report = inspect(base_url, renderer, "/render-changes-field")
    assert value_of(report, Channel.RAW_DOM) != value_of(report, Channel.RENDERED_DOM)


def test_endpoint_value_matches_the_rendered_value(base_url: str, renderer: Renderer) -> None:
    report = inspect(base_url, renderer, "/endpoint-matches-rendered")
    assert value_of(report, Channel.RENDERED_DOM) == value_of(report, Channel.NETWORK_JSON)
    endpoint = valued(report, Channel.NETWORK_JSON)[0]
    assert "/api/desk" in (endpoint.provenance.request or "")


def test_irrelevant_json_response_yields_no_observation(base_url: str, renderer: Renderer) -> None:
    report = inspect(base_url, renderer, "/irrelevant-json")
    assert not valued(report, Channel.NETWORK_JSON)
    assert report.acquisition.json_responses >= 1, "the response was observed, just not relevant"


def test_only_the_field_carrying_endpoint_is_surfaced(base_url: str, renderer: Renderer) -> None:
    report = inspect(base_url, renderer, "/multiple-endpoints")
    requests = " ".join(o.provenance.request or "" for o in valued(report, Channel.NETWORK_JSON))
    assert "/api/shelf" in requests
    assert "/api/telemetry" not in requests
    assert "/api/reviews" not in requests


def test_value_only_present_after_rendering(base_url: str, renderer: Renderer) -> None:
    report = inspect(base_url, renderer, "/no-useful-endpoint")
    assert not valued(report, Channel.RAW_DOM)
    assert valued(report, Channel.RENDERED_DOM)


def test_two_raw_representations_disagree(base_url: str, renderer: Renderer) -> None:
    report = inspect(base_url, renderer, "/representations-disagree")
    assert value_of(report, Channel.RAW_DOM) != value_of(report, Channel.STRUCTURED_DATA)


# --- repairs validated in the retest ---


def test_page_that_never_goes_idle_still_yields_evidence(base_url: str, renderer: Renderer) -> None:
    report = inspect(base_url, renderer, "/never-idle")
    assert report.acquisition.render_status is RenderStatus.PARTIAL_RENDER
    assert valued(report, Channel.RAW_DOM)


def test_navigation_failure_returns_evidence_instead_of_raising(renderer: Renderer) -> None:
    """Port 1 on loopback refuses, standing in for a transport-level navigation error."""
    observation = renderer.render("http://127.0.0.1:1/dead")
    assert observation.status is RenderStatus.RENDERING_FAILED
    assert observation.detail, "a failure with no detail is not evidence"


def test_render_failure_does_not_cost_the_raw_evidence(base_url: str) -> None:
    raw = fetch_raw(f"{base_url}/http-sufficient", allow_private=True)
    failed = RenderedObservation(
        url=raw.url,
        html="",
        responses=(),
        overflowed=False,
        seconds=0.0,
        status=RenderStatus.RENDERING_FAILED,
        detail="net::ERR_HTTP2_PROTOCOL_ERROR",
    )
    assert failed.status is RenderStatus.RENDERING_FAILED
    report = inspect(base_url, None, "/http-sufficient")
    assert valued(report, Channel.RAW_DOM), "raw evidence must survive a render failure"


def test_html_entity_currency_parses_as_currency_not_amount() -> None:
    """`&#8377;4400` parsed as the amount 8377 and garbled a whole report."""
    money = _money("&#8377;4400")
    assert isinstance(money, MoneyType)
    assert str(money.amount) == "4400"
    assert money.currency == "INR"


def test_unlabelled_currency_text_is_discovered(base_url: str, renderer: Renderer) -> None:
    report = inspect(base_url, renderer, "/unlabelled-price")
    found = [o for o in report.observations if o.normalized_value is not None]
    assert any(amount_of(o) == "42.00" for o in found)
    assert any("unlabelled" in (o.provenance.selector or "") for o in found)


def test_several_unlabelled_amounts_are_all_kept(base_url: str, renderer: Renderer) -> None:
    report = inspect(base_url, renderer, "/unlabelled-two-prices")
    amounts = {amount_of(o) for o in report.observations if o.normalized_value is not None}
    assert {"9.00", "19.00"} <= amounts, "one value was silently chosen over the other"


def test_currency_amount_inside_prose_is_not_a_price(base_url: str, renderer: Renderer) -> None:
    """ssl.com's '$1.75M warranty' is a warranty figure, not a price."""
    report = inspect(base_url, renderer, "/currency-in-prose")
    assert not [o for o in report.observations if o.normalized_value is not None]


def test_labelled_pages_still_governed_by_the_declared_rule() -> None:
    """The fallback is reached only when no element is marked as a price, so the
    neighbouring-product and dimension protections in the preflight corpus are untouched."""
    manifest = json.loads(Path("realworld/preflight/manifest.json").read_text())
    checked = 0
    for page in manifest["pages"]:
        source = Path("realworld/preflight/pages") / f"{page['id']}.html"
        if not source.exists() or page["expected_visible_price"] is None:
            continue
        html = source.read_text()
        candidates = from_dom(html)
        assert len(candidates) == 1, page["id"]
        value = candidates[0].value
        assert isinstance(value, MoneyValue), page["id"]
        assert str(value.amount) == page["expected_visible_price"], page["id"]
        assert "unlabelled" not in (candidates[0].provenance.selector or ""), page["id"]
        checked += 1
    assert checked >= PREFLIGHT_PRICED_PAGES, "the preflight corpus was not exercised"


def test_report_text_is_stable_across_runs(base_url: str, renderer: Renderer) -> None:
    first = render(inspect(base_url, renderer, "/multiple-endpoints"))
    second = render(inspect(base_url, renderer, "/multiple-endpoints"))
    assert _without_timings(first) == _without_timings(second)


def _without_timings(text: str) -> str:
    return "\n".join(line for line in text.splitlines() if "HTTP    " not in line)


@pytest.mark.parametrize(
    "url",
    ["file:///etc/passwd", "http://localhost:8080/x", "http://127.0.0.1/x", "http://10.0.0.1/x"],
)
def test_unsafe_targets_are_refused(url: str) -> None:
    with pytest.raises(UnsafeTargetError):
        check_target(url)
