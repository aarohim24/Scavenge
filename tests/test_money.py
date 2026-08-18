"""Monetary parsing for the real-world instrument, including the two bugs that
invalidated the first pilot."""

from __future__ import annotations

from decimal import Decimal

import pytest

from realworld.money import Money, ParseFailure, detect_currency, parse_money


@pytest.mark.parametrize(
    ("text", "amount", "currency"),
    [
        ("3,99 €", "3.99", "EUR"),
        ("3.99 €", "3.99", "EUR"),
        ("€1.234,56", "1234.56", "EUR"),
        ("€1,234.56", "1234.56", "EUR"),
        ("$1,234.56", "1234.56", "USD"),
        ("£3.99", "3.99", "GBP"),
        ("3.99 EUR", "3.99", "EUR"),
        ("1999", "1999", None),
        ("₹1,999", "1999", "INR"),
        ("$1,234", "1234", "USD"),
        ("1\xa0234,56 €", "1234.56", "EUR"),
        ("1 234,56 €", "1234.56", "EUR"),
        ("€1.234.567,89", "1234567.89", "EUR"),
        ("Hind 3,99€", "3.99", "EUR"),
    ],
)
def test_required_formats_parse_exactly(text: str, amount: str, currency: str | None) -> None:
    result = parse_money(text)

    assert isinstance(result, Money), result
    assert result.amount == Decimal(amount)
    assert result.currency == currency


def test_regression_european_decimal_comma_is_not_truncated() -> None:
    """The invalid pilot turned `3,99€` into 3, which would fake a conflict."""
    result = parse_money("3,99€")

    assert isinstance(result, Money)
    assert result.amount == Decimal("3.99")
    assert result.amount != Decimal(3)


def test_regression_decimal_price_is_not_rounded_to_int() -> None:
    """The invalid pilot turned JSON-LD `3.99` into 4 via int(round(...))."""
    result = parse_money("3.99")

    assert isinstance(result, Money)
    assert result.amount == Decimal("3.99")
    assert result.amount != Decimal(4)


def test_the_two_regressions_no_longer_disagree() -> None:
    """`3,99€` in the DOM and `3.99` in JSON-LD are the same price, not a conflict."""
    dom = parse_money("3,99€")
    jsonld = parse_money("3.99", currency_hint="EUR")

    assert isinstance(dom, Money)
    assert isinstance(jsonld, Money)
    assert dom.amount == jsonld.amount


def test_amount_is_decimal_not_float() -> None:
    result = parse_money("0.10 EUR")
    other = parse_money("0.20 EUR")

    assert isinstance(result, Money)
    assert isinstance(other, Money)
    assert isinstance(result.amount, Decimal)
    # The canonical value must not inherit binary floating point error.
    assert result.amount + other.amount == Decimal("0.30")


@pytest.mark.parametrize("text", ["1,234", "1.234", "€1,234", "€1.234"])
def test_ambiguous_grouping_is_reported_not_guessed(text: str) -> None:
    """Three trailing digits with no currency or language evidence is unresolvable."""
    assert parse_money(text) is ParseFailure.AMBIGUOUS_SEPARATOR


def test_language_resolves_ambiguity_when_currency_cannot() -> None:
    """EUR is written both ways, so the page's language is the deciding evidence."""
    german = parse_money("€1.234", language="de")
    irish_english = parse_money("€1,234", language="en")

    assert isinstance(german, Money)
    assert isinstance(irish_english, Money)
    assert german.amount == Decimal("1234")
    assert irish_english.amount == Decimal("1234")


def test_absence_of_digits_is_distinct_from_malformed() -> None:
    assert parse_money("Price unavailable") is ParseFailure.NO_DIGITS
    assert parse_money("") is ParseFailure.NO_DIGITS


def test_currency_detection() -> None:
    assert detect_currency("3,99 €") == "EUR"
    assert detect_currency("USD 12") == "USD"
    assert detect_currency("12") is None
