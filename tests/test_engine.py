"""Engine tests: the evidence model, determinism, and the two supported fields.

The integration fixture deliberately disagrees with itself across channels. Nothing here
asserts which value is "right" — that judgement is outside the engine.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from decimal import Decimal
from typing import Any

import pytest

from fixtures.scavenge.server import probe_fixture_server
from scavenge.acquire import Renderer, rendering_session
from scavenge.engine import UnknownFieldError, _observations, inspect_field
from scavenge.models import (
    MAX_VALUED_OBSERVATIONS,
    SCHEMA_VERSION,
    AvailabilityState,
    AvailabilityValue,
    Candidate,
    Channel,
    EvidenceReport,
    MoneyValue,
    Observation,
    ObservationStatus,
    Provenance,
    RenderStatus,
    comparable,
    comparison_key,
)
from scavenge.render import render


@pytest.fixture(scope="module")
def base_url() -> Iterator[str]:
    with probe_fixture_server() as url:
        yield url


@pytest.fixture(scope="module")
def renderer() -> Iterator[Renderer]:
    with rendering_session(allow_private=True) as active:
        yield active


def amount_of(observation: Observation) -> str:
    """Narrow the value union in one place instead of at every assertion."""
    value = observation.normalized_value
    assert isinstance(value, MoneyValue)
    return str(value.amount)


def state_of(observation: Observation) -> AvailabilityState:
    value = observation.normalized_value
    assert isinstance(value, AvailabilityValue)
    return value.state


def inspect(base_url: str, renderer: Renderer, path: str, field: str) -> EvidenceReport:
    return inspect_field(f"{base_url}{path}", field, renderer=renderer, allow_private=True)


def by_channel(report: EvidenceReport, channel: Channel) -> list[Observation]:
    return [o for o in report.observations if o.channel is channel]


def test_integration_price_evidence_across_four_channels(base_url: str, renderer: Renderer) -> None:
    report = inspect(base_url, renderer, "/integration", "price")
    values = {o.channel: o for o in report.observations if o.normalized_value is not None}
    assert values[Channel.RAW_DOM].normalized_value == MoneyValue(Decimal("99.00"), "USD")
    assert amount_of(values[Channel.STRUCTURED_DATA]) == "99.00"
    assert amount_of(values[Channel.RENDERED_DOM]) == "79.00"
    assert amount_of(values[Channel.NETWORK_JSON]) == "79.00"


def test_public_report_makes_no_comparison_claims(base_url: str, renderer: Renderer) -> None:
    """v0.1 publishes observations, not relations. Every DIFFERENT the engine produced on
    real storefronts compared two different entities — see OSS-FINAL-CORRECTNESS.md."""
    report = inspect(base_url, renderer, "/integration", "price").to_dict()
    assert "relations" not in report
    for banned in ("EQUAL", "DIFFERENT", "UNCOMPARABLE"):
        assert banned not in json.dumps(report)


def test_integration_availability_disagrees_across_render(
    base_url: str, renderer: Renderer
) -> None:
    report = inspect(base_url, renderer, "/integration", "availability")
    states = {o.channel: state_of(o) for o in report.observations if o.normalized_value}
    assert states[Channel.RAW_DOM] is AvailabilityState.IN_STOCK
    assert states[Channel.STRUCTURED_DATA] is AvailabilityState.IN_STOCK
    assert states[Channel.RENDERED_DOM] is AvailabilityState.OUT_OF_STOCK


def test_absent_channels_are_absent_not_invented(base_url: str, renderer: Renderer) -> None:
    report = inspect(base_url, renderer, "/http-sufficient", "price")
    assert not by_channel(report, Channel.STRUCTURED_DATA)
    assert by_channel(report, Channel.RAW_DOM)


def test_multiple_candidates_are_all_preserved(base_url: str, renderer: Renderer) -> None:
    report = inspect(base_url, renderer, "/unlabelled-two-prices", "price")
    amounts = {amount_of(o) for o in report.observations if o.normalized_value is not None}
    assert {"9.00", "19.00"} <= amounts, "a candidate was silently elected"


def test_unparsed_values_keep_their_raw_and_are_marked(base_url: str, renderer: Renderer) -> None:
    report = inspect(base_url, renderer, "/integration", "availability")
    for observation in report.observations:
        if observation.normalized_value is None:
            assert observation.status is ObservationStatus.PARSE_FAILURE
            assert observation.raw


def test_partial_render_is_recorded_not_raised(base_url: str, renderer: Renderer) -> None:
    report = inspect(base_url, renderer, "/never-idle", "price")
    assert report.acquisition.render_status is RenderStatus.PARTIAL_RENDER
    assert by_channel(report, Channel.RAW_DOM), "raw evidence lost on a partial render"


def test_skipping_the_browser_is_recorded_as_not_attempted(base_url: str) -> None:
    report = inspect_field(
        f"{base_url}/http-sufficient", "price", renderer=None, allow_private=True
    )
    assert report.acquisition.render_status is RenderStatus.NOT_ATTEMPTED
    assert not by_channel(report, Channel.RENDERED_DOM)


def test_unsupported_field_raises_rather_than_returning_empty_evidence(base_url: str) -> None:
    with pytest.raises(UnknownFieldError):
        inspect_field(f"{base_url}/integration", "colour", renderer=None, allow_private=True)


# Timings are measurements of this run, not observations, so they are excluded from the
# determinism comparison. The claim is that report *generation* is deterministic — not
# that a live URL always yields the same bytes. See README, "Determinism".
TIMING_KEYS = ("http_seconds", "render_seconds")


def _deterministic(report: dict[str, Any]) -> str:
    body = {k: v for k, v in report.items() if k != "acquisition"}
    body["acquisition"] = {k: v for k, v in report["acquisition"].items() if k not in TIMING_KEYS}
    return json.dumps(body, sort_keys=True)


def test_report_serialization_is_deterministic(base_url: str, renderer: Renderer) -> None:
    first = inspect(base_url, renderer, "/integration", "price").to_dict()
    second = inspect(base_url, renderer, "/integration", "price").to_dict()
    assert _deterministic(first) == _deterministic(second)
    assert first["schema_version"] == SCHEMA_VERSION
    assert isinstance(first["observations"][0]["normalized_value"]["amount"], str)


def test_human_output_leads_with_evidence_not_a_recommendation(
    base_url: str, renderer: Renderer
) -> None:
    text = render(inspect(base_url, renderer, "/integration", "price"))
    assert "raw_dom:0" in text
    assert "PROVENANCE" in text or "source:" in text
    for banned in ("SUGGESTED", "RECOMMEND", "MAY BE SUFFICIENT", "APPEARS NECESSARY"):
        assert banned not in text.upper()


@pytest.mark.parametrize(
    ("left", "right", "same"),
    [
        ("0.00", "0.0", True),  # found by the real-URL MCP smoke test
        ("99.00", "99", True),
        ("1234.50", "1234.5", True),
        ("99.00", "99.01", False),
    ],
)
def test_amounts_compare_numerically_not_textually(left: str, right: str, same: bool) -> None:
    a = comparison_key(MoneyValue(Decimal(left), "USD"))
    b = comparison_key(MoneyValue(Decimal(right), "USD"))
    assert (a == b) is same
    assert (hash(a) == hash(b)) is same or not same


def test_same_amount_in_different_currencies_is_never_equal() -> None:
    usd = MoneyValue(Decimal("10.00"), "USD")
    cad = MoneyValue(Decimal("10.00"), "CAD")
    assert not comparable(usd, cad)


def test_excess_candidates_are_dropped_loudly_not_silently() -> None:
    """A page can carry dozens of amounts. The cap is real, so it must be announced."""
    crowd = [
        (
            Channel.EMBEDDED_STATE,
            Candidate(MoneyValue(Decimal(str(n)), "USD"), str(n), Provenance()),
        )
        for n in range(MAX_VALUED_OBSERVATIONS + 5)
    ]
    observations, warnings = _observations(crowd)
    assert len(observations) == MAX_VALUED_OBSERVATIONS
    assert warnings
    assert "dropped" in warnings[0]


def test_challenge_page_is_named_and_its_values_are_not_read(
    base_url: str, renderer: Renderer
) -> None:
    """A block must not become evidence: reading a price off an interstitial would be a
    fabricated observation."""
    report = inspect(base_url, renderer, "/blocked-render", "price")
    assert report.acquisition.render_status is RenderStatus.BLOCKED_OR_CHALLENGED
    assert "Just a moment" in report.acquisition.render_detail
    assert not by_channel(report, Channel.RENDERED_DOM), "read a value off a challenge page"
    assert by_channel(report, Channel.RAW_DOM), "raw evidence was lost to the block"
    assert any("block or challenge" in w for w in report.warnings)


def test_empty_page_with_a_captcha_is_a_challenge(base_url: str, renderer: Renderer) -> None:
    report = inspect(base_url, renderer, "/captcha-wall", "price")
    assert report.acquisition.render_status is RenderStatus.BLOCKED_OR_CHALLENGED


def test_captcha_alongside_real_content_is_not_a_block(base_url: str, renderer: Renderer) -> None:
    """Checkout pages carry captchas. Calling those blocked would discard real evidence."""
    report = inspect(base_url, renderer, "/captcha-with-content", "price")
    assert report.acquisition.render_status is not RenderStatus.BLOCKED_OR_CHALLENGED
    assert by_channel(report, Channel.RENDERED_DOM)


def test_ordinary_pages_are_never_called_blocked(base_url: str, renderer: Renderer) -> None:
    for path in ("/http-sufficient", "/integration", "/render-changes-field"):
        report = inspect(base_url, renderer, path, "price")
        assert report.acquisition.render_status is not RenderStatus.BLOCKED_OR_CHALLENGED


def test_challenged_raw_body_is_named_and_its_values_are_not_read(base_url: str) -> None:
    """Found in release validation: a raw body reading 'Are you a human?' was treated as an
    ordinary page, so the cheap channels could report a challenge page's numbers."""
    report = inspect_field(f"{base_url}/blocked-http", "price", renderer=None, allow_private=True)
    assert report.acquisition.http_challenge
    assert "human" in report.acquisition.http_challenge
    assert not report.observations, "read a value out of a challenged raw body"
    assert any("raw HTTP response looks like a block" in w for w in report.warnings)


def test_ordinary_raw_bodies_carry_no_challenge_signal(base_url: str) -> None:
    report = inspect_field(
        f"{base_url}/http-sufficient", "price", renderer=None, allow_private=True
    )
    assert report.acquisition.http_challenge == ""
    assert report.observations


def test_boolean_flags_matching_the_price_key_are_not_candidates(base_url: str) -> None:
    """`isClubPrice: false` produced eight junk observations on a real storefront."""
    report = inspect_field(
        f"{base_url}/boolean-price-flags", "price", renderer=None, allow_private=True
    )
    raws = [o.raw for o in report.observations]
    assert "False" not in raws
    assert any(amount_of(o) == "27.50" for o in report.observations if o.normalized_value)


def test_script_mentioning_challenge_wording_is_not_a_block(
    base_url: str, renderer: Renderer
) -> None:
    """Interstitial phrases are matched in visible text only. A page whose script contains
    the words is an ordinary page, and its raw evidence must survive."""
    report = inspect(base_url, renderer, "/blocked-render", "price")
    assert by_channel(report, Channel.RAW_DOM), "raw evidence lost to a phrase inside a script"
