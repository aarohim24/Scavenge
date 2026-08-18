"""Arm E: cross-source conflict detection from the cheap document alone."""

from __future__ import annotations

import ast
from collections.abc import Iterator
from pathlib import Path

import pytest

import crawlbench.verification.evidence
from crawlbench.execution.http import fetch
from crawlbench.extraction import extract_product
from crawlbench.models import Candidate, EvidenceSource, load_tasks
from crawlbench.verification.evidence import (
    Decision,
    conflicting_sources,
    normalize,
    verify,
)
from crawlbench.verification.experiment import FIELDS, cheap_extractions, naive_accepts
from fixtures.server import GROUND_TRUTH_PATH, serve_fixtures

TASKS = load_tasks(GROUND_TRUTH_PATH)
TASKS_BY_ID = {task.task_id: task for task in TASKS}
CURRENT_PRICE = 1999
STALE_PRICE = 2999
COMPLETE = {"name": "P", "price": CURRENT_PRICE, "currency": "INR"}

# Declared before arm E was implemented or run, from the cheap HTML alone.
PREDECLARED_DETECTABILITY = {
    "conflicting-prices": "DETECTABLE_FROM_CHEAP_EVIDENCE",
    "stale-html-price": "NOT_DETECTABLE_FROM_CHEAP_EVIDENCE",
    "deals-303": "NOT_DETECTABLE_FROM_CHEAP_EVIDENCE",
}


@pytest.fixture(scope="module")
def base_url() -> Iterator[str]:
    with serve_fixtures() as url:
        yield url


def _candidates(*triples: tuple[str, object, EvidenceSource]) -> tuple[Candidate, ...]:
    return tuple(Candidate(field=f, value=v, source=s) for f, v, s in triples)


def test_candidate_source_is_preserved(base_url: str) -> None:
    extraction = extract_product(fetch(f"{base_url}/conflicting-prices").html)

    prices = {(c.source, c.value) for c in extraction.candidates if c.field == "price"}

    assert (EvidenceSource.DOM, STALE_PRICE) in prices
    assert (EvidenceSource.JSON_LD, CURRENT_PRICE) in prices


def test_the_scored_record_is_unchanged_by_candidate_collection(base_url: str) -> None:
    """Scoring must see exactly what it saw before E existed."""
    extraction = extract_product(fetch(f"{base_url}/static-product").html)

    assert extraction.record == {
        "name": "Example Product",
        "price": CURRENT_PRICE,
        "currency": "INR",
    }
    assert set(extraction.record) == set(FIELDS)


def test_agreeing_independent_sources_are_accepted() -> None:
    candidates = _candidates(
        ("price", CURRENT_PRICE, EvidenceSource.DOM),
        ("price", CURRENT_PRICE, EvidenceSource.JSON_LD),
    )

    assert conflicting_sources("price", candidates) == ()
    assert verify(COMPLETE, candidates, FIELDS) is Decision.ACCEPT


def test_normalised_equivalents_are_not_a_conflict() -> None:
    candidates = _candidates(
        ("price", "1,999", EvidenceSource.DOM),
        ("price", CURRENT_PRICE, EvidenceSource.JSON_LD),
        ("currency", "inr", EvidenceSource.ATTRIBUTE),
        ("currency", "INR", EvidenceSource.JSON_LD),
    )

    assert normalize("price", "1,999") == CURRENT_PRICE
    assert normalize("currency", "inr") == "INR"
    assert verify(COMPLETE, candidates, FIELDS) is Decision.ACCEPT


def test_conflicting_independent_sources_are_rejected() -> None:
    candidates = _candidates(
        ("price", STALE_PRICE, EvidenceSource.DOM),
        ("price", CURRENT_PRICE, EvidenceSource.JSON_LD),
    )

    assert conflicting_sources("price", candidates)
    assert verify(COMPLETE, candidates, FIELDS) is Decision.REJECT_CONFLICT


def test_repeated_evidence_from_one_source_is_not_independent() -> None:
    """Two selectors on the same channel are one observation, not two.

    Neither a second agreeing DOM value nor a disagreeing one changes the decision,
    because v0.4 acts only on disagreement between channels.
    """
    agreeing = _candidates(
        ("price", CURRENT_PRICE, EvidenceSource.DOM),
        ("price", CURRENT_PRICE, EvidenceSource.DOM),
    )
    disagreeing = _candidates(
        ("price", CURRENT_PRICE, EvidenceSource.DOM),
        ("price", STALE_PRICE, EvidenceSource.DOM),
    )

    assert conflicting_sources("price", agreeing) == ()
    assert conflicting_sources("price", disagreeing) == ()
    assert verify(COMPLETE, disagreeing, FIELDS) is Decision.ACCEPT


def test_a_missing_required_field_is_rejected() -> None:
    assert verify({"name": "P", "price": CURRENT_PRICE}, (), FIELDS) is Decision.REJECT_INCOMPLETE
    assert verify({**COMPLETE, "price": None}, (), FIELDS) is Decision.REJECT_INCOMPLETE


def test_conflicting_prices_is_detected_from_cheap_evidence(base_url: str) -> None:
    """E's predeclared win: the raw HTML contradicts itself before any JavaScript."""
    extraction = extract_product(fetch(f"{base_url}/conflicting-prices").html)

    assert PREDECLARED_DETECTABILITY["conflicting-prices"] == "DETECTABLE_FROM_CHEAP_EVIDENCE"
    assert verify(extraction.record, extraction.candidates, FIELDS) is Decision.REJECT_CONFLICT


@pytest.mark.parametrize("task_id", ["stale-html-price", "deals-303"])
def test_stale_prices_without_a_cheap_contradiction_are_accepted(
    base_url: str, task_id: str
) -> None:
    """Predeclared as undetectable, and E must not be credited with catching them.

    The cheap document offers one source for the price. E has no evidence that a
    different value will appear after JavaScript runs, and does not pretend to.
    """
    task = TASKS_BY_ID[task_id]
    extraction = extract_product(fetch(f"{base_url}{task.path}").html)

    assert PREDECLARED_DETECTABILITY[task_id] == "NOT_DETECTABLE_FROM_CHEAP_EVIDENCE"
    assert conflicting_sources("price", extraction.candidates) == ()
    assert verify(extraction.record, extraction.candidates, FIELDS) is Decision.ACCEPT


def test_agreeing_sources_fixture_is_accepted(base_url: str) -> None:
    """E must not score well merely by distrusting every multi-source page."""
    extraction = extract_product(fetch(f"{base_url}/agreeing-sources").html)

    sources = {c.source for c in extraction.candidates if c.field == "price"}

    assert len(sources) > 1
    assert verify(extraction.record, extraction.candidates, FIELDS) is Decision.ACCEPT


def test_arm_e_cannot_reach_ground_truth_or_browser_output() -> None:
    """Structural guard, as for E0."""
    module = ast.parse(Path(crawlbench.verification.evidence.__file__).read_text(encoding="utf-8"))
    imported = {
        alias.asname or alias.name
        for node in ast.walk(module)
        if isinstance(node, ast.ImportFrom | ast.Import)
        for alias in node.names
    }

    for forbidden in ("Task", "ResultState", "score", "load_tasks", "ExecutionMode", "Document"):
        assert forbidden not in imported


def test_all_three_verifiers_judge_identical_records(base_url: str) -> None:
    records, candidates, states = cheap_extractions(base_url, TASKS)

    assert len(records) == len(candidates) == len(states) == len(TASKS)
    for record, candidate in zip(records, candidates, strict=True):
        # naive and E consume the same record; E additionally reads its candidates.
        assert isinstance(naive_accepts(record), bool)
        assert verify(record, candidate, FIELDS) in set(Decision)
