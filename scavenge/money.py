"""Currency-aware monetary parsing for the real-world pilot instrument.

Written after the invalid pilot, which used an INR/integer-oriented rule that turned
`3,99 €` into `3` and `3.99` into `4`. Those two bugs would have manufactured a
conflict on essentially every European price page, so the canonical representation is
now `Decimal` plus a currency, never a binary float and never a bare int.

Separator conventions are resolved from evidence — the currency, or the page's
language — and never guessed. When the evidence is insufficient the result is an
explicit failure, because a wrong amount is far more damaging to this experiment than
a missing one.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import StrEnum

SYMBOL_CURRENCIES = {"€": "EUR", "$": "USD", "£": "GBP", "₹": "INR", "¥": "JPY", "zł": "PLN"}
CURRENCY_CODES = frozenset(
    {"EUR", "USD", "GBP", "INR", "JPY", "CHF", "SEK", "NOK", "DKK", "PLN", "CAD", "AUD"}
)

# Currencies whose conventional decimal mark is '.', so ',' groups thousands.
DOT_DECIMAL_CURRENCIES = frozenset({"USD", "GBP", "INR", "CAD", "AUD", "JPY"})
# Currencies whose conventional decimal mark is ',', so '.' groups thousands.
COMMA_DECIMAL_CURRENCIES = frozenset({"SEK", "NOK", "DKK", "PLN"})
# EUR is deliberately in neither: it is written both ways depending on locale.

DOT_DECIMAL_LANGUAGES = frozenset({"en", "ga", "mt"})
COMMA_DECIMAL_LANGUAGES = frozenset(
    {"de", "fr", "es", "it", "nl", "pt", "fi", "et", "lv", "lt", "sk", "sl", "pl", "sv", "da", "cs"}
)

_SPACES = dict.fromkeys(map(ord, "\xa0   ⁠"), " ")
_NUMBER = re.compile(r"\d[\d.,\s]*\d|\d")
_GROUPED_BY_SPACE = re.compile(r"^\d{1,3}(?: \d{3})+(?:[.,]\d+)?$")
_CODE = re.compile(r"\b([A-Z]{3})\b")

_DECIMAL_PLACES_MAX = 2
_GROUP_SIZE = 3


class ParseFailure(StrEnum):
    """Why a price string produced no value. Never conflated with 'no price here'."""

    NO_DIGITS = "NO_DIGITS"
    AMBIGUOUS_SEPARATOR = "AMBIGUOUS_SEPARATOR"
    MALFORMED = "MALFORMED"


@dataclass(frozen=True)
class Money:
    amount: Decimal
    currency: str | None

    def __str__(self) -> str:
        return f"{self.amount} {self.currency or '?'}"


def detect_currency(text: str) -> str | None:
    """Currency from an explicit symbol or ISO code in the text."""
    for symbol, code in SYMBOL_CURRENCIES.items():
        if symbol in text:
            return code
    for match in _CODE.finditer(text.upper()):
        if match.group(1) in CURRENCY_CODES:
            return match.group(1)
    return None


def _decimal_separator_for(currency: str | None, language: str | None) -> str | None:
    """Which mark is the decimal point, judged from currency then language."""
    if currency in DOT_DECIMAL_CURRENCIES:
        return "."
    if currency in COMMA_DECIMAL_CURRENCIES:
        return ","
    if language:
        primary = language.split("-")[0].lower()
        if primary in DOT_DECIMAL_LANGUAGES:
            return "."
        if primary in COMMA_DECIMAL_LANGUAGES:
            return ","
    return None


def parse_money(
    text: str,
    *,
    currency_hint: str | None = None,
    language: str | None = None,
) -> Money | ParseFailure:
    """Parse a price string into `Decimal` + currency, or say explicitly why not."""
    if not text:
        return ParseFailure.NO_DIGITS

    cleaned = text.translate(_SPACES)
    currency = detect_currency(cleaned) or currency_hint

    match = _NUMBER.search(cleaned)
    if match is None:
        return ParseFailure.NO_DIGITS
    token = match.group().strip()

    # A space can only be a thousands separator, and only in a well-formed group.
    if " " in token:
        if not _GROUPED_BY_SPACE.fullmatch(token):
            return ParseFailure.MALFORMED
        token = token.replace(" ", "")

    digits = _resolve_separators(token, currency, language)
    if isinstance(digits, ParseFailure):
        return digits

    try:
        return Money(amount=Decimal(digits), currency=currency)
    except InvalidOperation:
        return ParseFailure.MALFORMED


def _resolve_separators(  # noqa: PLR0911 - each return is a distinct, named outcome.
    token: str, currency: str | None, language: str | None
) -> str | ParseFailure:
    """Turn a raw numeric token into a plain decimal string, or fail explicitly."""
    has_dot, has_comma = "." in token, "," in token

    if not has_dot and not has_comma:
        return token

    if has_dot and has_comma:
        # The rightmost mark is the decimal point; the other groups thousands.
        decimal_mark = "." if token.rfind(".") > token.rfind(",") else ","
        grouping = "," if decimal_mark == "." else "."
        return token.replace(grouping, "").replace(decimal_mark, ".")

    mark = "." if has_dot else ","
    occurrences = token.count(mark)
    tail = len(token.rsplit(mark, maxsplit=1)[-1])

    if occurrences > 1:
        # Repeated marks can only be grouping: 1.234.567
        if tail != _GROUP_SIZE:
            return ParseFailure.MALFORMED
        return token.replace(mark, "")

    if tail <= _DECIMAL_PLACES_MAX:
        return token.replace(mark, ".")

    if tail == _GROUP_SIZE:
        # `1,234` is 1234 or 1.234 depending on locale. Decide only on evidence.
        convention = _decimal_separator_for(currency, language)
        if convention is None:
            return ParseFailure.AMBIGUOUS_SEPARATOR
        if convention == mark:
            return token.replace(mark, ".")
        return token.replace(mark, "")

    return ParseFailure.MALFORMED
