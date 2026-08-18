"""Price candidate extraction with provenance: visible DOM text and schema.org offers.

Repairs the second bug that invalidated the first pilot. The old DOM rule skipped any
price-labelled element that contained another price-labelled element, which on real
sites discards exactly the elements holding the number and keeps the ones holding
labels. It extracted nothing on 55 of 55 pages.

The replacement keeps every candidate with its provenance and selects among them by a
declared, site-independent rule, so a later audit can see what was chosen and why.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from enum import StrEnum

from selectolax.parser import HTMLParser, Node

from scavenge.money import Money, ParseFailure, detect_currency, parse_money

_PRICE_ATTR = re.compile(r"price", re.IGNORECASE)
# Presentational attributes only. `itemprop` is microdata, a different channel, and
# folding it into the DOM channel would inflate agreement between channels.
_DOM_MARKER_ATTRS = ("class", "id", "data-testid")
_MAX_PRICE_TEXT = 40
# Conventionally non-current prices: struck-through, "was", list/RRP. Excluding these
# is a general presentation convention, not a per-site rule.
_SUPERSEDED = re.compile(r"was|old|strike|through|original|list|rrp|regular|previous", re.I)
_SUPERSEDED_TAGS = frozenset({"s", "del", "strike"})


class Channel(StrEnum):
    DOM = "DOM"
    JSON_LD = "JSON_LD"


class ChannelStatus(StrEnum):
    """A parse failure and an absent channel are different outcomes and stay different."""

    OK = "OK"
    PARSE_FAILURE = "PARSE_FAILURE"
    ABSENT = "ABSENT"
    MULTIPLE_DISTINCT = "MULTIPLE_DISTINCT"


@dataclass(frozen=True)
class PriceCandidate:
    channel: Channel
    raw: str
    path: str
    money: Money | None
    failure: ParseFailure | None
    superseded: bool = False


@dataclass(frozen=True)
class ChannelResult:
    channel: Channel
    status: ChannelStatus
    chosen: PriceCandidate | None
    candidates: tuple[PriceCandidate, ...]
    selection_reason: str


def page_language(html: str) -> str | None:
    node = HTMLParser(html).css_first("html")
    return node.attributes.get("lang") if node else None


def _within_superseded(node: Node) -> bool:
    current: Node | None = node
    for _ in range(4):
        if current is None:
            return False
        if current.tag in _SUPERSEDED_TAGS:
            return True
        current = current.parent
    return False


def _dom_path(node: Node) -> str:
    parts = []
    current: Node | None = node
    for _ in range(3):
        if current is None or current.tag in {"html", "-undef"}:
            break
        classes = (current.attributes.get("class") or "").split()
        parts.append(current.tag + ("." + classes[0] if classes else ""))
        current = current.parent
    return ">".join(reversed(parts))


def dom_prices(html: str, language: str | None = None) -> ChannelResult:
    """Every price-labelled element that parses, plus which one was chosen and why.

    Selection rule, declared and site-independent: among elements whose class, id or
    data-testid mentions "price" and whose own text parses as money, discard those
    marked as superseded prices (struck through, "was", list/RRP) and take the first
    remaining one in document order. Candidate text must carry a currency indicator.
    A product detail page conventionally shows the current price of its own product
    before any related-product prices.

    An earlier draft took the shortest text instead. The preflight corpus showed that
    picks a neighbouring product's `3€` over this product's `3,99€`, so the rule was
    corrected before any prevalence measurement. See PILOT-PROTOCOL-CHANGES.md.
    """
    tree = HTMLParser(html)
    candidates: list[PriceCandidate] = []

    for node in tree.css("*"):
        marker = " ".join(str(node.attributes.get(a) or "") for a in _DOM_MARKER_ATTRS)
        if not _PRICE_ATTR.search(marker):
            continue
        text = (node.text(deep=True, strip=True) or "").strip()
        if not text or len(text) > _MAX_PRICE_TEXT:
            continue
        # A price carries a currency. Without one, a "price"-classed container is
        # something else — the preflight corpus showed dimensions ("70-120 cm")
        # being read as an amount.
        if detect_currency(text) is None:
            continue
        parsed = parse_money(text, language=language)
        candidates.append(
            PriceCandidate(
                channel=Channel.DOM,
                raw=text,
                path=_dom_path(node),
                money=parsed if isinstance(parsed, Money) else None,
                failure=parsed if isinstance(parsed, ParseFailure) else None,
                superseded=bool(_SUPERSEDED.search(marker)) or _within_superseded(node),
            )
        )

    return _select(Channel.DOM, candidates, "first current-price element in document order")


def jsonld_prices(html: str) -> ChannelResult:
    """Prices under schema.org Product/Offer blocks, each with a JSON pointer."""
    tree = HTMLParser(html)
    candidates: list[PriceCandidate] = []

    for index, node in enumerate(tree.css('script[type="application/ld+json"]')):
        raw = node.text().strip()
        if not raw:
            continue
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            candidates.append(
                PriceCandidate(
                    channel=Channel.JSON_LD,
                    raw=raw[:60],
                    path=f"script[{index}]",
                    money=None,
                    failure=ParseFailure.MALFORMED,
                )
            )
            continue
        _walk_jsonld(parsed, f"script[{index}]", candidates)

    return _select(Channel.JSON_LD, candidates, "first schema.org price in document order")


def _walk_jsonld(node: object, pointer: str, out: list[PriceCandidate], depth: int = 0) -> None:
    max_depth = 8
    if depth > max_depth:
        return
    if isinstance(node, dict):
        if "price" in node:
            raw = node["price"]
            currency = node.get("priceCurrency")
            parsed = parse_money(
                str(raw), currency_hint=currency if isinstance(currency, str) else None
            )
            out.append(
                PriceCandidate(
                    channel=Channel.JSON_LD,
                    raw=str(raw),
                    path=f"{pointer}/price",
                    money=parsed if isinstance(parsed, Money) else None,
                    failure=parsed if isinstance(parsed, ParseFailure) else None,
                )
            )
        for key, value in node.items():
            _walk_jsonld(value, f"{pointer}/{key}", out, depth + 1)
    elif isinstance(node, list):
        for index, item in enumerate(node):
            _walk_jsonld(item, f"{pointer}/{index}", out, depth + 1)


def _select(channel: Channel, candidates: list[PriceCandidate], reason: str) -> ChannelResult:
    if not candidates:
        return ChannelResult(channel, ChannelStatus.ABSENT, None, (), "no candidate elements")

    parsed = [c for c in candidates if c.money is not None and not c.superseded]
    if not parsed:
        return ChannelResult(
            channel,
            ChannelStatus.PARSE_FAILURE,
            None,
            tuple(candidates),
            "candidates found but none parsed",
        )

    chosen = parsed[0]

    distinct = {(c.money.amount, c.money.currency) for c in parsed if c.money}
    status = ChannelStatus.MULTIPLE_DISTINCT if len(distinct) > 1 else ChannelStatus.OK
    return ChannelResult(channel, status, chosen, tuple(candidates), reason)
