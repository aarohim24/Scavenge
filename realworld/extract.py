"""Arm E channel comparison, plus re-exports of extraction that now lives in `evidence`.

The candidate extraction below `evidence/pricing.py` is the canonical implementation and is
shared with the product. `Comparison`/`compare_channels` stay here because they encode Arm
E's pilot semantics, which are research-only and must not enter the engine.
"""

from __future__ import annotations

from enum import StrEnum

from scavenge.pricing import (  # noqa: F401 - re-export for historical importers
    Channel,
    ChannelResult,
    ChannelStatus,
    PriceCandidate,
    dom_prices,
    jsonld_prices,
    page_language,
)


class Comparison(StrEnum):
    """Outcome of comparing two channels, per PILOT-PROTOCOL.md sections 3 and 13."""

    AGREE = "AGREE"
    CONFLICT = "CONFLICT"
    AMBIGUOUS_CURRENCY = "AMBIGUOUS_CURRENCY"
    AMBIGUOUS_MULTIPLE_OFFERS = "AMBIGUOUS_MULTIPLE_OFFERS"
    NOT_COMPARABLE = "NOT_COMPARABLE"


def compare_channels(dom: ChannelResult, jsonld: ChannelResult) -> Comparison:
    """Only same-currency, single-valued channels can conflict.

    The canary found a page whose DOM shows USD while its JSON-LD offers CAD. Comparing
    the amounts alone reported a conflict that does not exist, which is exactly the
    error that would inflate measured prevalence.
    """
    if dom.chosen is None or jsonld.chosen is None:
        return Comparison.NOT_COMPARABLE
    if dom.chosen.money is None or jsonld.chosen.money is None:
        return Comparison.NOT_COMPARABLE
    if ChannelStatus.MULTIPLE_DISTINCT in {dom.status, jsonld.status}:
        return Comparison.AMBIGUOUS_MULTIPLE_OFFERS

    left, right = dom.chosen.money, jsonld.chosen.money
    if left.currency and right.currency and left.currency != right.currency:
        return Comparison.AMBIGUOUS_CURRENCY
    return Comparison.AGREE if left.amount == right.amount else Comparison.CONFLICT


__all__ = [
    "Channel",
    "ChannelResult",
    "ChannelStatus",
    "Comparison",
    "PriceCandidate",
    "compare_channels",
    "dom_prices",
    "jsonld_prices",
    "page_language",
]
