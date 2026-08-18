"""D5 (subject scope) and D6 (currency evidence): the two defects that blocked release.

Each case here reproduces a measured real-world failure from OSS-RELEASE-VALIDATION.md.
The point is not that relations disappear — it is that *wrong* relations disappear while
right ones survive, which the retention tests below pin.
"""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal

import pytest

from fixtures.scavenge.server import probe_fixture_server
from scavenge.acquire import Renderer, rendering_session
from scavenge.engine import inspect_field
from scavenge.models import (
    PAGE_SUBJECT,
    Channel,
    EvidenceReport,
    MoneyValue,
    Subject,
    SubjectMatch,
    SubjectScope,
    comparable,
    subject_match,
)

MIN_SIBLINGS = 2
MIN_EQUAL_RELATIONS = 2


@pytest.fixture(scope="module")
def base_url() -> Iterator[str]:
    with probe_fixture_server() as url:
        yield url


@pytest.fixture(scope="module")
def renderer() -> Iterator[Renderer]:
    with rendering_session(allow_private=True) as active:
        yield active


def inspect(base: str, renderer: Renderer | None, path: str, field: str) -> EvidenceReport:
    return inspect_field(f"{base}{path}", field, renderer=renderer, allow_private=True)


def values(report: EvidenceReport) -> set[str]:
    return {str(o.normalized_value) for o in report.observations if o.normalized_value is not None}


def scopes(report: EvidenceReport) -> set[SubjectScope]:
    return {o.subject.scope for o in report.observations}


# --- D5: financing table (canadiantire.ca) ---


def test_financing_amounts_produce_no_price_relations(base_url: str, renderer: Renderer) -> None:
    report = inspect(base_url, renderer, "/financing-table", "price")
    assert report.observations, "the amounts should still be reported as evidence"
    assert all(o.subject.scope is SubjectScope.UNKNOWN for o in report.observations)


def test_labelled_product_price_wins_over_a_financing_table(
    base_url: str, renderer: Renderer
) -> None:
    """With a labelled price present the fallback never runs, so the table is not read."""
    report = inspect(base_url, renderer, "/financing-with-labelled-price", "price")
    amounts = {
        str(o.normalized_value.amount)
        for o in report.observations
        if isinstance(o.normalized_value, MoneyValue)
    }
    assert amounts == {"499.00"}


# --- D5: search payload (lakeland.co.uk) ---


def test_search_hits_do_not_contradict_the_page_product(base_url: str, renderer: Renderer) -> None:
    report = inspect(base_url, renderer, "/search-payload", "availability")
    siblings = [o for o in report.observations if o.subject.scope is SubjectScope.SIBLING]
    assert len(siblings) >= MIN_SIBLINGS, "the search hits should be sibling entities"
    page = [o for o in report.observations if o.subject.scope is SubjectScope.PAGE]
    assert page, "the page's own availability must survive"


# --- D5: store locator (naturisimo) ---


def test_store_locator_rows_do_not_contradict_the_page_product(
    base_url: str, renderer: Renderer
) -> None:
    report = inspect(base_url, renderer, "/store-locator", "availability")
    dom = [o for o in report.observations if o.channel is Channel.RAW_DOM]
    assert dom, "the per-store statuses are still reported"
    assert all(o.subject.scope is SubjectScope.UNKNOWN for o in dom)


# --- D5 retention: the case scoping must not destroy ---


def test_same_product_across_channels_is_still_observed(base_url: str, renderer: Renderer) -> None:
    """Scoping must not suppress observations themselves — only the claim that they match."""
    report = inspect(base_url, renderer, "/integration", "price")
    assert {"99.00 USD", "79.00 USD"} <= values(report)
    assert SubjectScope.PAGE in scopes(report)


def test_subject_match_rules() -> None:
    sibling_a = Subject(SubjectScope.SIBLING, "/hits/0", "")
    sibling_b = Subject(SubjectScope.SIBLING, "/hits/1", "")
    unknown = Subject(SubjectScope.UNKNOWN, "", "")
    assert subject_match(PAGE_SUBJECT, PAGE_SUBJECT) is SubjectMatch.SAME
    assert subject_match(sibling_a, sibling_a) is SubjectMatch.SAME
    assert subject_match(sibling_a, sibling_b) is SubjectMatch.DIFFERENT
    assert subject_match(PAGE_SUBJECT, sibling_a) is SubjectMatch.DIFFERENT
    assert subject_match(PAGE_SUBJECT, unknown) is SubjectMatch.UNKNOWN


# --- D6: currency evidence ---


def currency_of(report: EvidenceReport) -> set[str | None]:
    return {
        o.normalized_value.currency
        for o in report.observations
        if isinstance(o.normalized_value, MoneyValue)
    }


def test_explicit_structured_currency_wins(base_url: str) -> None:
    report = inspect(base_url, None, "/financing-with-labelled-price", "price")
    assert currency_of(report) == {"CAD"}


def test_canadian_page_evidence_yields_cad(base_url: str) -> None:
    report = inspect(base_url, None, "/canadian-price", "price")
    assert currency_of(report) == {"CAD"}


def test_dollar_without_evidence_has_no_currency(base_url: str) -> None:
    """`$` names a dozen currencies. With nothing to go on, the amount survives and the
    currency does not."""
    report = inspect(base_url, None, "/no-locale-price", "price")
    assert currency_of(report) == {None}
    assert any("499.00" in o.raw for o in report.observations)


def test_us_page_evidence_yields_usd(base_url: str) -> None:
    report = inspect(base_url, None, "/http-sufficient", "price")
    assert currency_of(report) == {"USD"}


def test_unambiguous_symbol_needs_no_page_evidence(base_url: str) -> None:
    report = inspect(base_url, None, "/euro-price", "price")
    assert currency_of(report) == {"EUR"}


def test_unknown_currency_is_uncomparable_against_a_known_one() -> None:
    known = MoneyValue(Decimal("499.00"), "USD")
    unknown = MoneyValue(Decimal("499.00"), None)
    assert not comparable(known, unknown)
    assert comparable(unknown, MoneyValue(Decimal("499.00"), None))


def test_related_product_prices_do_not_unscope_the_labelled_price(
    base_url: str, renderer: Renderer
) -> None:
    """Retention guard. Marking a page's chosen price unknown merely because the page also
    shows other prices destroyed three correct EQUAL relations on a real storefront."""
    report = inspect(base_url, renderer, "/neighbouring-prices", "price")
    dom = [o for o in report.observations if o.channel is Channel.RAW_DOM]
    assert dom
    assert dom[0].subject.scope is SubjectScope.PAGE
    assert "49.95 USD" in values(report)
