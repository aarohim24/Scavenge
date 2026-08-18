"""The `price` field adapter: candidate money values per channel, with provenance.

Two correctness rules learned from real pages live here:

* **Subject scope.** A page marks nothing as a price, or marks several — then a value found
  in it is not evidence of *this product's* price. A financing table produced eight such
  values in release validation. Those candidates are kept, with provenance, but their
  subject is unknown so they are never correlated against the page.
* **Currency.** "$" names at least a dozen currencies. It is resolved from declared
  evidence or left unknown; it is never assumed to be USD.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from selectolax.parser import HTMLParser

from scavenge.acquire import NetworkResponse
from scavenge.channels import decode, embedded_payloads, find_keys, sibling_subject
from scavenge.context import PageContext
from scavenge.models import (
    PAGE_SUBJECT,
    Candidate,
    MoneyValue,
    Provenance,
    Subject,
    SubjectScope,
)
from scavenge.money import Money, ParseFailure, parse_money
from scavenge.pricing import ChannelStatus, dom_prices, jsonld_prices, page_language

_PRICE_KEY = re.compile(r"price", re.IGNORECASE)
_CURRENCY_KEY = re.compile(r"currency", re.IGNORECASE)
# Fallback for markup that marks nothing as a price — CSS-module sites where every class is
# a hash. The candidate must be an element's own short text that is essentially just the
# amount: at most this many characters may surround the currency-and-amount token.
_MAX_SURROUNDING = 8
_MAX_TEXT = 40
_CURRENCY_AMOUNT = re.compile(r"(?:\$|£|€|₹|¥|zł)\s?\d[\d.,]*")
_AMBIGUOUS_SYMBOL = "$"


def _unknown(reason: str) -> Subject:
    return Subject(SubjectScope.UNKNOWN, "", reason)


def _parse(raw: object, currency: str | None = None) -> Money | ParseFailure:
    """`isClubPrice: false` matched the price key on a real page; a boolean is never an amount."""
    if isinstance(raw, bool):
        return ParseFailure.NO_DIGITS
    return parse_money(decode(raw), currency_hint=currency)


def _value(money: Money, text: str, context: PageContext | None) -> MoneyValue:
    """Currency by declared precedence: explicit code, then page evidence, else unknown.

    Only the bare "$" is re-opened — £, € and ₹ have one plausible reading, and an explicit
    ISO code already won inside the parser.
    """
    currency = money.currency
    if currency == "USD" and _AMBIGUOUS_SYMBOL in text and "USD" not in text.upper():
        currency = context.currency if context else None
    return MoneyValue(amount=money.amount, currency=currency)


def from_dom(html: str, context: PageContext | None = None) -> list[Candidate]:
    """Labelled price elements; the unlabelled fallback only when the page marks none."""
    result = dom_prices(html, language=page_language(html))
    chosen = result.chosen
    if chosen is None or chosen.money is None:
        return _unlabelled(html, context)

    # Several labelled prices does **not** unscope the chosen one: `dom_prices` picks by a
    # declared site-independent rule, and marking it unknown destroyed correct correlations
    # on pages that merely show related-product prices. The note still reports the
    # multiplicity. Only a page that labels *nothing* leaves the subject unresolved.
    multiple = result.status is ChannelStatus.MULTIPLE_DISTINCT
    note = "several distinct prices on the page" if multiple else ""
    return [
        Candidate(
            _value(chosen.money, chosen.raw, context),
            chosen.raw,
            Provenance(selector=chosen.path),
            note,
            PAGE_SUBJECT,
        )
    ]


def _unlabelled(html: str, context: PageContext | None) -> list[Candidate]:
    reason = "found by currency-bearing text; the page marks no element as a price"
    found: dict[tuple[str, str], Candidate] = {}
    for node in HTMLParser(html).css("*"):
        text = (node.text(deep=False, strip=True) or "").strip()
        if not text or len(text) > _MAX_TEXT:
            continue
        match = _CURRENCY_AMOUNT.search(text)
        if match is None or len(text) - len(match.group(0)) > _MAX_SURROUNDING:
            continue
        money = _parse(text)
        if not isinstance(money, Money):
            continue
        value = _value(money, text, context)
        found.setdefault(
            (str(value.amount), value.currency or ""),
            Candidate(
                value,
                text,
                Provenance(selector=f"{node.tag} (unlabelled)"),
                reason,
                _unknown(reason),
            ),
        )
    return list(found.values())


def from_structured(html: str, context: PageContext | None = None) -> list[Candidate]:
    result = jsonld_prices(html)
    chosen = result.chosen
    if chosen is None or chosen.money is None:
        return []
    multiple = result.status is ChannelStatus.MULTIPLE_DISTINCT
    note = "several distinct offers" if multiple else ""
    return [
        Candidate(
            _value(chosen.money, chosen.raw, context),
            chosen.raw,
            Provenance(pointer=chosen.path),
            note,
            PAGE_SUBJECT,
        )
    ]


def from_embedded(html: str, context: PageContext | None = None) -> list[Candidate]:
    out: list[Candidate] = []
    for script, payload in embedded_payloads(html):
        matches = find_keys(payload, _PRICE_KEY)
        for pointer, raw, siblings in matches:
            if isinstance(raw, bool):
                continue
            out.append(
                _json_candidate(
                    raw,
                    siblings,
                    Provenance(pointer=pointer, script=script),
                    sibling_subject(pointer, matches),
                    context,
                )
            )
    return out


def from_network(
    responses: Sequence[NetworkResponse], context: PageContext | None = None
) -> list[Candidate]:
    out: list[Candidate] = []
    for response in responses:
        if response.payload is None:
            continue
        matches = find_keys(response.payload, _PRICE_KEY)
        for pointer, raw, siblings in matches:
            if isinstance(raw, bool):
                continue
            out.append(
                _json_candidate(
                    raw,
                    siblings,
                    Provenance(
                        pointer=pointer,
                        request=f"{response.method} {response.url}",
                        content_type=response.content_type,
                    ),
                    sibling_subject(pointer, matches),
                    context,
                )
            )
    return out


def _json_candidate(
    raw: object,
    siblings: dict[str, str],
    provenance: Provenance,
    subject: Subject,
    context: PageContext | None,
) -> Candidate:
    currency = next((v for k, v in siblings.items() if _CURRENCY_KEY.search(k)), None)
    money = _parse(raw, currency)
    text = str(raw) if currency else f"{_AMBIGUOUS_SYMBOL}{raw}"
    return Candidate(
        _value(money, text, context) if isinstance(money, Money) else None,
        str(raw),
        provenance,
        "" if isinstance(money, Money) else f"did not parse as money ({money})",
        subject,
    )
