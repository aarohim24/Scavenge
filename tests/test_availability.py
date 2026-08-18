"""Availability normalization: only meanings we can read plainly become states."""

from __future__ import annotations

import pytest

from scavenge.availability import from_dom, from_structured, normalize
from scavenge.models import AvailabilityState, AvailabilityValue

IN_STOCK = ("In Stock", "in stock", "Available", "InStock", "true")
OUT_OF_STOCK = ("Out of Stock", "Sold out", "unavailable", "false")
# Text that mentions stock without stating one. Promoting these to a state would be
# inference, which belongs to the agent, not the engine.
NOT_A_STATE = (
    "Notify me when back in stock",
    "Only 3 left — order soon",
    "Check stock in your local store",
    "probably",
    "",
)


@pytest.mark.parametrize("text", IN_STOCK)
def test_in_stock_phrases(text: str) -> None:
    value = normalize(text)
    assert value is not None
    assert value.state is AvailabilityState.IN_STOCK


@pytest.mark.parametrize("text", OUT_OF_STOCK)
def test_out_of_stock_phrases(text: str) -> None:
    value = normalize(text)
    assert value is not None
    assert value.state is AvailabilityState.OUT_OF_STOCK


@pytest.mark.parametrize("text", NOT_A_STATE)
def test_unrecognised_text_yields_no_state(text: str) -> None:
    assert normalize(text) is None


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://schema.org/InStock", AvailabilityState.IN_STOCK),
        ("http://schema.org/OutOfStock", AvailabilityState.OUT_OF_STOCK),
        ("https://schema.org/SoldOut", AvailabilityState.OUT_OF_STOCK),
    ],
)
def test_schema_org_availability_urls(url: str, expected: AvailabilityState) -> None:
    value = normalize(url)
    assert value is not None
    assert value.state is expected


def test_schema_org_value_we_do_not_model_stays_raw() -> None:
    assert normalize("https://schema.org/PreOrder") is None


def test_visible_in_stock_element_is_found_with_provenance() -> None:
    html = '<html><body><div class="stock-status">In stock</div></body></html>'
    candidates = from_dom(html)
    assert len(candidates) == 1
    value = candidates[0].value
    assert isinstance(value, AvailabilityValue)
    assert value.state is AvailabilityState.IN_STOCK
    assert candidates[0].provenance.selector


def test_unmarked_availability_text_is_not_scanned_for() -> None:
    """No marker attribute, no candidate: the engine does not read prose for meaning."""
    html = "<html><body><p>This item is in stock at most branches</p></body></html>"
    assert not from_dom(html)


def test_structured_availability_keeps_pointer_and_raw() -> None:
    html = (
        '<html><head><script type="application/ld+json">'
        '{"@type":"Product","offers":{"availability":"https://schema.org/OutOfStock"}}'
        "</script></head><body></body></html>"
    )
    candidates = from_structured(html)
    assert len(candidates) == 1
    value = candidates[0].value
    assert isinstance(value, AvailabilityValue)
    assert value.state is AvailabilityState.OUT_OF_STOCK
    assert candidates[0].provenance.pointer
    assert candidates[0].raw == "https://schema.org/OutOfStock"
