"""Page-level evidence the field adapters need: currency, and the page's own identifiers.

Cheap and deterministic. No GeoIP, no external calls, no country service — only what the
document and its host already state.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from urllib.parse import urlparse

from selectolax.parser import HTMLParser

from scavenge.channels import embedded_payloads

# Hosts whose country implies one currency unambiguously. Deliberately short: a TLD is only
# usable evidence where the country has a single obvious currency and no common alternative.
_TLD_CURRENCY = {
    "ca": "CAD",
    "au": "AUD",
    "nz": "NZD",
    "sg": "SGD",
    "uk": "GBP",
    "ie": "EUR",
    "de": "EUR",
    "fr": "EUR",
    "es": "EUR",
    "it": "EUR",
    "nl": "EUR",
    "pt": "EUR",
    "se": "SEK",
    "no": "NOK",
    "dk": "DKK",
    "pl": "PLN",
    "ch": "CHF",
    "in": "INR",
    "jp": "JPY",
    "br": "BRL",
    "mx": "MXN",
    "za": "ZAR",
}
_LANG_REGION_CURRENCY = {
    "en-ca": "CAD",
    "fr-ca": "CAD",
    "en-au": "AUD",
    "en-nz": "NZD",
    "en-gb": "GBP",
    "en-sg": "SGD",
    "en-in": "INR",
    "en-za": "ZAR",
    "pt-br": "BRL",
    "es-mx": "MXN",
    "en-us": "USD",
    "sv-se": "SEK",
    "nb-no": "NOK",
    "da-dk": "DKK",
}
_CURRENCY_CODE = re.compile(r'"priceCurrency"\s*:\s*"([A-Z]{3})"')


@dataclass(frozen=True)
class PageContext:
    """What the page itself says about currency, plus the identifiers that name its subject."""

    url: str
    currency: str | None
    currency_reason: str
    identifiers: frozenset[str]


def build(url: str, html: str) -> PageContext:
    currency, reason = _currency(url, html)
    return PageContext(url, currency, reason, _identifiers(html))


def _currency(url: str, html: str) -> tuple[str | None, str]:
    """Declared precedence: structured data, then an explicit region, then the host TLD."""
    declared = _CURRENCY_CODE.search(html)
    if declared:
        return declared.group(1), "priceCurrency in structured data"

    root = HTMLParser(html).css_first("html")
    lang = ((root.attributes.get("lang") if root else None) or "").lower()
    if lang in _LANG_REGION_CURRENCY:
        return _LANG_REGION_CURRENCY[lang], f"<html lang={lang!r}>"

    host = urlparse(url).netloc.lower()
    tld = host.rsplit(".", 1)[-1] if "." in host else ""
    if tld == "uk" and host.endswith(".co.uk"):
        return "GBP", "host .co.uk"
    if tld in _TLD_CURRENCY:
        return _TLD_CURRENCY[tld], f"host .{tld}"
    return None, "no deterministic currency evidence"


def _identifiers(html: str) -> frozenset[str]:
    """schema.org Product identity: sku, productID, gtin*, mpn, url."""
    found: set[str] = set()
    tree = HTMLParser(html)
    for node in tree.css('script[type="application/ld+json"]'):
        _collect(_load(node.text()), found)
    for label, payload in embedded_payloads(html):  # noqa: B007 - label unused, payload is not
        _collect(payload, found, depth_budget=4)
    return frozenset(found)


def _load(text: str) -> object:
    try:
        return json.loads(text.strip())
    except (json.JSONDecodeError, ValueError):
        return None


_ID_KEYS = ("sku", "productid", "gtin", "gtin8", "gtin12", "gtin13", "gtin14", "mpn")


def _collect(node: object, out: set[str], depth: int = 0, depth_budget: int = 8) -> None:
    if depth > depth_budget:
        return
    if isinstance(node, dict):
        for key, value in node.items():
            if key.lower() in _ID_KEYS and isinstance(value, str | int):
                out.add(f"{key.lower()}:{value}")
            else:
                _collect(value, out, depth + 1, depth_budget)
    elif isinstance(node, list):
        for item in node[:20]:
            _collect(item, out, depth + 1, depth_budget)
