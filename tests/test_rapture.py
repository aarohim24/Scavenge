"""Arm E0: faithfulness to the paper, and what it can and cannot detect."""

from __future__ import annotations

import ast
from collections.abc import Iterator
from pathlib import Path

import pytest

import crawlbench.verification.rapture
from crawlbench.execution.http import fetch
from crawlbench.extraction import extract_product
from crawlbench.models import load_tasks
from crawlbench.verification.experiment import (
    FIELDS,
    cheap_extractions,
    naive_accepts,
    reference_extractions,
)
from crawlbench.verification.rapture import (
    ALL_FEATURES,
    FEATURES,
    fit,
)
from fixtures.server import GROUND_TRUTH_PATH, REFERENCE_PATHS, serve_fixtures

TASKS = load_tasks(GROUND_TRUTH_PATH)
# Kushmerick, AAAI-99: worked feature values for the string '20 Maple St.'.
PAPER_EXAMPLE = "20 Maple St."
PAPER_VALUES = {
    "digit_density": 2 / 12,
    "letter_density": 7 / 12,
    "upper_density": 2 / 12,
    "lower_density": 5 / 12,
    "punctuation_density": 1 / 12,
    "html_density": 0.0,
    "length": 12.0,
    "word_count": 3.0,
    "mean_word_length": 10 / 3,
}
TAU = 0.5
LOW_TAU = 0.01


@pytest.fixture(scope="module")
def base_url() -> Iterator[str]:
    with serve_fixtures() as url:
        yield url


@pytest.fixture(scope="module")
def reference(base_url: str) -> list[dict[str, object]]:
    return reference_extractions(base_url)


def test_features_match_the_papers_worked_example() -> None:
    """Every one of the nine features, against the values printed in the paper."""
    assert set(FEATURES) == set(PAPER_VALUES)
    for feature, expected in PAPER_VALUES.items():
        assert FEATURES[feature](PAPER_EXAMPLE) == pytest.approx(expected)


def test_features_handle_empty_and_degenerate_strings() -> None:
    for feature in ALL_FEATURES:
        value = FEATURES[feature]("")
        assert value == 0.0
        assert value == value  # noqa: PLR0124 - explicit NaN guard.


def test_verifier_is_deterministic(reference: list[dict[str, object]]) -> None:
    record = {"name": "Copper Kettle", "price": 1000, "currency": "INR"}

    first = fit(reference, fields=FIELDS)
    second = fit(reference, fields=FIELDS)

    assert first.feature_params == second.feature_params
    assert first.verification_params == second.verification_params
    assert first.verification_probability(record) == second.verification_probability(record)
    assert first.accepts(record, TAU) == second.accepts(record, TAU)


def test_ground_truth_is_not_reachable_from_the_verifier() -> None:
    """Structural guard: E0 decides from content statistics, never from labels."""
    module = ast.parse(Path(crawlbench.verification.rapture.__file__).read_text(encoding="utf-8"))
    imported = {
        alias.asname or alias.name
        for node in ast.walk(module)
        if isinstance(node, ast.ImportFrom | ast.Import)
        for alias in node.names
    }

    for forbidden in ("Task", "ResultState", "score", "load_tasks", "GROUND_TRUTH_PATH"):
        assert forbidden not in imported


def test_accepts_in_distribution_records(reference: list[dict[str, object]]) -> None:
    """Stated over the whole reference set rather than one hand-picked record.

    It does not accept all of them: one reference label is its own distribution's
    outlier and is rejected even at the loosest threshold, which is worth knowing
    before reading E0's false-reject rate on the benchmark.
    """
    verifier = fit(reference, fields=FIELDS)

    accepted = sum(verifier.accepts(record, LOW_TAU) for record in reference)

    assert accepted > len(reference) // 2
    assert accepted < len(reference)


def test_the_papers_half_threshold_rejects_half_of_its_own_reference_labels(
    reference: list[dict[str, object]],
) -> None:
    """Calibration, not a defect: tau = 1/2 means "above the verified mean".

    Roughly half of any reference set sits below its own mean, so tau = 1/2 discards
    known-good labels by construction. This is why E0's false-reject rate is high at
    the paper's headline threshold, and it must be read alongside the frontier.
    """
    verifier = fit(reference, fields=FIELDS)

    accepted_at_half = sum(verifier.accepts(record, TAU) for record in reference)
    accepted_at_low = sum(verifier.accepts(record, LOW_TAU) for record in reference)

    assert accepted_at_half <= len(reference) // 2 + 1
    assert accepted_at_low > accepted_at_half


def test_rejects_strongly_shifted_content(reference: list[dict[str, object]]) -> None:
    """Markup leaking into a field is the drift RAPTURE was built to catch."""
    verifier = fit(reference, fields=FIELDS)
    shifted = {
        "name": "<td><b>Copper Kettle</b></td><td>unavailable</td>",
        "price": 1000,
        "currency": "INR",
    }

    assert not verifier.accepts(shifted, TAU)


def test_a_missing_field_is_rejected(reference: list[dict[str, object]]) -> None:
    """The paper rejects a wrapper whose execution is undefined."""
    verifier = fit(reference, fields=FIELDS)

    assert not verifier.accepts({"name": "Copper Kettle", "currency": "INR"}, TAU)


def test_stale_price_is_indistinguishable_from_the_correct_price(
    reference: list[dict[str, object]],
) -> None:
    """The known limitation, stated as a test: 1999 and 2999 are the same to RAPTURE.

    Every one of the nine features is identical, so no threshold and no dependency
    assumption can separate a stale price from the correct one.
    """
    assert {f: FEATURES[f]("1999") for f in ALL_FEATURES} == {
        f: FEATURES[f]("2999") for f in ALL_FEATURES
    }

    verifier = fit(reference, fields=FIELDS)
    correct = {"name": "Stale Price Product", "price": 1999, "currency": "INR"}
    stale = {"name": "Stale Price Product", "price": 2999, "currency": "INR"}

    assert verifier.verification_probability(correct) == verifier.verification_probability(stale)
    assert verifier.accepts(correct, TAU) == verifier.accepts(stale, TAU)


def test_naive_and_e0_judge_identical_records(
    base_url: str, reference: list[dict[str, object]]
) -> None:
    """The comparison is only meaningful if both verifiers see the same extractions."""
    records, _candidates, states = cheap_extractions(base_url, TASKS)
    verifier = fit(reference, fields=FIELDS)

    assert len(records) == len(TASKS) == len(states)
    for task, record in zip(TASKS, records, strict=True):
        expected = extract_product(fetch(f"{base_url}{task.path}").html).record
        assert record == expected
        # Both decisions are computed from this one record and nothing else.
        assert isinstance(naive_accepts(record), bool)
        assert isinstance(verifier.accepts(record, TAU), bool)


def test_reference_pages_are_not_benchmark_tasks() -> None:
    """Reference and evaluation sets must not overlap."""
    task_paths = {task.path for task in TASKS}

    assert not task_paths & set(REFERENCE_PATHS)
