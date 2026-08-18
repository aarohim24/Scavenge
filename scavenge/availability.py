"""The `availability` field adapter.

Deliberately narrow: only representations whose meaning is unambiguous — schema.org
availability values and clearly labelled visible text. Anything else keeps its raw value
and gets **no** normalized value, rather than being promoted to a semantic "unknown" we
never observed. There is no NLP here and no inference from marketing prose.
"""

from __future__ import annotations

import json
import re
from collections.abc import Sequence

from selectolax.parser import HTMLParser

from scavenge.acquire import NetworkResponse
from scavenge.channels import decode, embedded_payloads, find_keys, sibling_subject
from scavenge.models import (
    PAGE_SUBJECT,
    AvailabilityState,
    AvailabilityValue,
    Candidate,
    Provenance,
    Subject,
    SubjectScope,
)
from scavenge.pricing import _dom_path  # noqa: PLC2701 - the same provenance format

_KEY = re.compile(r"availability|in_?stock|stock_?status", re.IGNORECASE)
_MARKER = re.compile(r"availability|stock|in-stock|instock", re.IGNORECASE)
_MARKER_ATTRS = ("class", "id", "data-testid")
_MAX_TEXT = 40
# One state on a page is unambiguous. Two different ones mean we cannot tell which belongs
# to the product — a store locator lists a status per branch.
_MIN_CONFLICTING = 2

# Exact phrases only. A substring test would read "out of stock" as in stock, and
# "notify me when back in stock" is a subscription prompt, not a state.
_IN_STOCK = frozenset({"in stock", "instock", "available", "in-stock", "add to cart", "buy now"})
_OUT_OF_STOCK = frozenset(
    {"out of stock", "outofstock", "sold out", "unavailable", "out-of-stock", "soldout"}
)
_SCHEMA = {
    "instock": AvailabilityState.IN_STOCK,
    "outofstock": AvailabilityState.OUT_OF_STOCK,
    "soldout": AvailabilityState.OUT_OF_STOCK,
}


def normalize(raw: str) -> AvailabilityValue | None:
    """A state only when the text says so plainly; otherwise None, and the raw survives."""
    text = decode(raw).strip().lower()
    if text.startswith(("http://schema.org/", "https://schema.org/")):
        return _state(_SCHEMA.get(text.rsplit("/", 1)[-1]))
    if text in _IN_STOCK:
        return AvailabilityValue(AvailabilityState.IN_STOCK)
    if text in _OUT_OF_STOCK:
        return AvailabilityValue(AvailabilityState.OUT_OF_STOCK)
    if text in {"true", "false"}:
        return AvailabilityValue(
            AvailabilityState.IN_STOCK if text == "true" else AvailabilityState.OUT_OF_STOCK
        )
    return None


def _state(state: AvailabilityState | None) -> AvailabilityValue | None:
    return AvailabilityValue(state) if state else None


def from_dom(html: str, _context: object = None) -> list[Candidate]:
    """Elements marked as stock/availability whose own text names a state.

    Several *different* states on one page means we cannot tell which is the product's — a
    store-locator list produced "In stock" and "Out of stock" side by side in release
    validation — so all of them become subject-unknown rather than contradicting each other.
    """
    found: dict[str, Candidate] = {}
    for node in HTMLParser(html).css("*"):
        marker = " ".join(str(node.attributes.get(a) or "") for a in _MARKER_ATTRS)
        if not _MARKER.search(marker):
            continue
        text = (node.text(deep=True, strip=True) or "").strip()
        if not text or len(text) > _MAX_TEXT:
            continue
        value = normalize(text)
        if value is None:
            continue
        found.setdefault(
            value.state.value, Candidate(value, text, Provenance(selector=_dom_path(node)))
        )
    values = list(found.values())
    if len(values) < _MIN_CONFLICTING:
        return values
    reason = "several conflicting availability states on the page"
    return [Candidate(c.value, c.raw, c.provenance, reason, _unknown(reason)) for c in values]


def _unknown(reason: str) -> Subject:
    return Subject(SubjectScope.UNKNOWN, "", reason)


def from_structured(html: str, _context: object = None) -> list[Candidate]:
    out: list[Candidate] = []
    for index, node in enumerate(HTMLParser(html).css('script[type="application/ld+json"]')):
        text = node.text().strip()
        if not text:
            continue
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            continue
        matches = find_keys(payload, _KEY)
        for pointer, raw, _ in matches:
            out.append(
                _candidate(
                    raw,
                    Provenance(pointer=f"script[{index}]{pointer}"),
                    sibling_subject(pointer, matches),
                )
            )
    return out


def from_embedded(html: str, _context: object = None) -> list[Candidate]:
    out: list[Candidate] = []
    for script, payload in embedded_payloads(html):
        matches = find_keys(payload, _KEY)
        for pointer, raw, _ in matches:
            out.append(
                _candidate(
                    raw,
                    Provenance(pointer=pointer, script=script),
                    sibling_subject(pointer, matches),
                )
            )
    return out


def from_network(responses: Sequence[NetworkResponse], _context: object = None) -> list[Candidate]:
    out: list[Candidate] = []
    for response in responses:
        if response.payload is None:
            continue
        matches = find_keys(response.payload, _KEY)
        for pointer, raw, _ in matches:
            out.append(
                _candidate(
                    raw,
                    Provenance(
                        pointer=pointer,
                        request=f"{response.method} {response.url}",
                        content_type=response.content_type,
                    ),
                    sibling_subject(pointer, matches),
                )
            )
    return out


def _candidate(raw: object, provenance: Provenance, subject: Subject = PAGE_SUBJECT) -> Candidate:
    value = normalize(str(raw))
    note = "" if value else "no availability state we recognise"
    return Candidate(value, str(raw), provenance, note, subject)
