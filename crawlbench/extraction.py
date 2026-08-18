"""Extraction of the product fields the fixtures require.

Deliberately small. This exists to make the benchmark meaningful, not to be a
general extraction framework. Fields the extractor cannot find are omitted from
the record rather than filled with a placeholder.
"""

from __future__ import annotations

import json
import re
from typing import Any

from selectolax.parser import HTMLParser

from crawlbench.models import Candidate, EvidenceSource, Extraction

_DIGITS = re.compile(r"\d[\d,]*")
_EMBEDDED_DATA = re.compile(r"window\.__CRAWLBENCH_DATA__\s*=\s*(\{.*?\})\s*;", re.DOTALL)


def extract_product(html: str) -> Extraction:  # noqa: PLR0912
    """Extract name, price, and currency from the fixture HTML."""
    tree = HTMLParser(html)
    record: dict[str, Any] = {}
    payloads = _structured_payloads(html)

    name = (
        _text(tree, "h1.product-title")
        or _table_value(tree, "name")
        or _payload_value(payloads, "name")
    )
    if name is not None:
        record["name"] = name

    price_node = tree.css_first("span.price")
    if price_node is not None:
        price = _parse_price(price_node.text())
        if price is not None:
            record["price"] = price
        currency = price_node.attributes.get("data-currency")
        if currency:
            record["currency"] = currency

    if "price" not in record:
        price_text = _table_value(tree, "price")
        if price_text is not None:
            price = _parse_price(price_text)
            if price is not None:
                record["price"] = price

    if "price" not in record:
        price = _payload_value(payloads, "price")
        if isinstance(price, int):
            record["price"] = price
        elif isinstance(price, str):
            parsed_price = _parse_price(price)
            if parsed_price is not None:
                record["price"] = parsed_price

    if "currency" not in record:
        currency = (
            _table_value(tree, "currency")
            or _payload_value(payloads, "currency")
            or _payload_value(payloads, "priceCurrency")
        )
        if isinstance(currency, str) and currency:
            record["currency"] = currency

    return Extraction(record=record, candidates=_collect_candidates(tree, payloads))


def _text(tree: HTMLParser, selector: str) -> str | None:
    node = tree.css_first(selector)
    if node is None:
        return None
    text = node.text().strip()
    return text or None


def _parse_price(raw: str) -> int | None:
    """Parse an integer minor-unit-free price out of display text such as '₹1,999'.

    Returns None when no digits are present, so that an empty or placeholder price
    is reported as a missing field instead of a wrong value.
    """
    match = _DIGITS.search(raw)
    if match is None:
        return None
    return int(match.group().replace(",", ""))


def _table_value(tree: HTMLParser, label: str) -> str | None:
    for row in tree.css("table.product tr"):
        cells = row.css("th, td")
        if len(cells) < _MIN_TABLE_CELLS:
            continue
        heading = cells[0].text().strip().lower()
        if heading == label.lower():
            value = cells[1].text().strip()
            return value or None
    return None


def _structured_payloads(html: str) -> list[tuple[EvidenceSource, dict[str, Any]]]:
    payloads: list[tuple[EvidenceSource, dict[str, Any]]] = []

    tree = HTMLParser(html)
    for node in tree.css('script[type="application/ld+json"]'):
        raw = node.text().strip()
        if not raw:
            continue
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            continue
        payloads.extend((EvidenceSource.JSON_LD, item) for item in _payload_dicts(parsed))

    for match in _EMBEDDED_DATA.finditer(html):
        try:
            parsed = json.loads(match.group(1))
        except json.JSONDecodeError:
            continue
        payloads.extend((EvidenceSource.EMBEDDED_JSON, item) for item in _payload_dicts(parsed))

    return payloads


def _payload_dicts(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        return [value]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    return []


def _payload_value(payloads: list[tuple[EvidenceSource, dict[str, Any]]], key: str) -> Any:
    for _, payload in payloads:
        if key in payload:
            return payload[key]
    return None


def _collect_candidates(
    tree: HTMLParser, payloads: list[tuple[EvidenceSource, dict[str, Any]]]
) -> tuple[Candidate, ...]:
    """Every value each channel offers, including ones `record` discarded.

    Unlike the record above, this does not stop at the first source that answers.
    """
    found: list[Candidate] = []

    def add(field: str, value: Any, source: EvidenceSource) -> None:
        if value is not None and value != "":
            found.append(Candidate(field=field, value=value, source=source))

    add("name", _text(tree, "h1.product-title"), EvidenceSource.DOM)
    add("name", _table_value(tree, "name"), EvidenceSource.DOM)

    price_node = tree.css_first("span.price")
    if price_node is not None:
        add("price", _parse_price(price_node.text()), EvidenceSource.DOM)
        add("currency", price_node.attributes.get("data-currency"), EvidenceSource.ATTRIBUTE)

    price_cell = _table_value(tree, "price")
    if price_cell is not None:
        add("price", _parse_price(price_cell), EvidenceSource.DOM)
    add("currency", _table_value(tree, "currency"), EvidenceSource.DOM)

    for source, payload in payloads:
        add("name", payload.get("name"), source)
        add("price", payload.get("price"), source)
        add("currency", payload.get("currency") or payload.get("priceCurrency"), source)

    return tuple(found)


_MIN_TABLE_CELLS = 2
