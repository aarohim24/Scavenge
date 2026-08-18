"""Instrument preflight: the extractor must reproduce independently recorded prices.

"Passes" means every page in the manifest matches on all four of: DOM channel status,
DOM chosen amount and currency, JSON-LD channel status and amount, and whether the two
channels conflict. Any single mismatch fails the suite, and no prevalence measurement
may be run until it is green.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from realworld.extract import (
    Channel,
    ChannelResult,
    ChannelStatus,
    Comparison,
    PriceCandidate,
    compare_channels,
    dom_prices,
    jsonld_prices,
    page_language,
)
from realworld.money import Money

PREFLIGHT = Path(__file__).parent.parent / "realworld" / "preflight"
MANIFEST = json.loads((PREFLIGHT / "manifest.json").read_text(encoding="utf-8"))["pages"]
CASES = [(page["id"], page) for page in MANIFEST]


def _html(page_id: str) -> str:
    return (PREFLIGHT / "pages" / f"{page_id}.html").read_text(encoding="utf-8")


def _amount(page: dict[str, Any], key: str) -> Decimal | None:
    value = page[key]
    return Decimal(str(value)) if value is not None else None


@pytest.mark.parametrize(("page_id", "page"), CASES, ids=[c[0] for c in CASES])
def test_dom_channel_matches_recorded_expectation(page_id: str, page: dict[str, Any]) -> None:
    html = _html(page_id)
    result = dom_prices(html, page_language(html))

    assert result.channel is Channel.DOM
    assert result.status == ChannelStatus(str(page["expected_dom_status"]))

    expected = _amount(page, "expected_visible_price")
    if expected is None:
        assert result.chosen is None
    else:
        assert result.chosen is not None
        assert result.chosen.money is not None
        assert result.chosen.money.amount == expected
        assert result.chosen.money.currency == page["expected_currency"]


@pytest.mark.parametrize(("page_id", "page"), CASES, ids=[c[0] for c in CASES])
def test_jsonld_channel_matches_recorded_expectation(page_id: str, page: dict[str, Any]) -> None:
    result = jsonld_prices(_html(page_id))

    assert result.status == ChannelStatus(str(page["expected_jsonld_status"]))

    expected = _amount(page, "expected_jsonld_price")
    if expected is None:
        assert result.chosen is None
    else:
        assert result.chosen is not None
        assert result.chosen.money is not None
        assert result.chosen.money.amount == expected


@pytest.mark.parametrize(("page_id", "page"), CASES, ids=[c[0] for c in CASES])
def test_conflict_detection_matches_expectation(page_id: str, page: dict[str, Any]) -> None:
    """The suite must detect a genuine conflict and must not invent one."""
    html = _html(page_id)
    dom, jsonld = dom_prices(html, page_language(html)), jsonld_prices(html)

    conflict = False
    if dom.chosen is not None and jsonld.chosen is not None:
        left, right = dom.chosen.money, jsonld.chosen.money
        conflict = left is not None and right is not None and left.amount != right.amount

    assert conflict == page["expect_conflict"]


def test_every_candidate_retains_provenance() -> None:
    """A later audit must be able to see what was considered and what was chosen."""
    html = _html("ikea-raecka")
    result = dom_prices(html, page_language(html))

    assert result.candidates
    assert result.selection_reason
    for candidate in result.candidates:
        assert candidate.channel is Channel.DOM
        assert candidate.raw
        assert candidate.path
        assert (candidate.money is None) != (candidate.failure is None)


def test_parse_failure_and_absence_are_different_statuses() -> None:
    failure = dom_prices(_html("dom-unparseable"), "en")
    absent = dom_prices(_html("no-price-anywhere"), "en")

    assert failure.status is ChannelStatus.PARSE_FAILURE
    assert absent.status is ChannelStatus.ABSENT
    assert failure.candidates
    assert not absent.candidates


def test_the_original_pilot_failure_no_longer_reproduces() -> None:
    """0 of 55 real pages yielded a DOM price under the old rule; this one now does."""
    html = _html("ikea-raecka")
    result = dom_prices(html, page_language(html))

    assert result.chosen is not None
    assert result.chosen.money is not None
    assert result.chosen.money.amount == Decimal("3.99")
    assert result.chosen.money.currency == "EUR"


@pytest.mark.parametrize(
    ("page_id", "expected"),
    [
        ("genuine-conflict", "CONFLICT"),
        ("multiple-offers", "AMBIGUOUS_MULTIPLE_OFFERS"),
        ("no-jsonld", "NOT_COMPARABLE"),
        ("dom-unparseable", "NOT_COMPARABLE"),
        ("ikea-raecka", "AMBIGUOUS_MULTIPLE_OFFERS"),
        ("sale-vs-list", "AGREE"),
        ("eu-comma-decimal", "AGREE"),
    ],
)
def test_channel_comparison_outcomes(page_id: str, expected: str) -> None:
    html = _html(page_id)
    result = compare_channels(dom_prices(html, page_language(html)), jsonld_prices(html))

    assert result.value == expected


def test_currency_mismatch_is_not_a_conflict() -> None:
    """A canary page showed DOM USD against JSON-LD CAD; that is ambiguity, not disagreement."""

    def channel(ch: Channel, amount: str, currency: str) -> ChannelResult:
        candidate = PriceCandidate(ch, amount, "p", Money(Decimal(amount), currency), None)
        return ChannelResult(ch, ChannelStatus.OK, candidate, (candidate,), "test")

    result = compare_channels(
        channel(Channel.DOM, "8.14", "USD"), channel(Channel.JSON_LD, "9.50", "CAD")
    )

    assert result is Comparison.AMBIGUOUS_CURRENCY
