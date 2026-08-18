"""Compatibility shim. `evidence.money` is the canonical owner of this behaviour.

The Arm E pilot code and its historical tests import from here. Moving the parser under
`evidence/` rather than copying it keeps one implementation, so the research record and
the product can never drift apart. Nothing was changed in the move.
"""

from scavenge.money import (  # noqa: F401 - re-export for historical importers
    COMMA_DECIMAL_CURRENCIES,
    COMMA_DECIMAL_LANGUAGES,
    CURRENCY_CODES,
    DOT_DECIMAL_CURRENCIES,
    DOT_DECIMAL_LANGUAGES,
    SYMBOL_CURRENCIES,
    Money,
    ParseFailure,
    detect_currency,
    parse_money,
)

__all__ = [
    "COMMA_DECIMAL_CURRENCIES",
    "COMMA_DECIMAL_LANGUAGES",
    "CURRENCY_CODES",
    "DOT_DECIMAL_CURRENCIES",
    "DOT_DECIMAL_LANGUAGES",
    "Money",
    "ParseFailure",
    "SYMBOL_CURRENCIES",
    "detect_currency",
    "parse_money",
]
