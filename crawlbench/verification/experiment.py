"""The E0 experiment: does RAPTURE-style verification beat a required-fields check?

Both verifiers see exactly the same cheap (HTTP) extractions. Ground truth scores the
decisions afterwards; it is never an input to either verifier.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from crawlbench.execution.http import fetch
from crawlbench.extraction import extract_product
from crawlbench.models import Candidate, ResultState, Task, load_tasks
from crawlbench.scoring import score
from crawlbench.verification import evidence
from crawlbench.verification.rapture import (
    ALL_FEATURES,
    HTML_DENSITY_ONLY,
    RaptureVerifier,
    fit,
)
from fixtures.server import GROUND_TRUTH_PATH, REFERENCE_PATHS, serve_fixtures

FIELDS = ("name", "price", "currency")
# Declared before any result was seen, and reported in full rather than filtered.
# 0.5 and 0.25 are the paper's own settings; the rest widen the sweep symmetrically.
THRESHOLDS = (0.01, 0.05, 0.10, 0.25, 0.50)
CONFIGURATIONS = (
    ("all-nine/equivalence", ALL_FEATURES, "equivalence"),
    ("html-density/independence", HTML_DENSITY_ONLY, "independence"),
)


def naive_accepts(record: Mapping[str, object]) -> bool:
    """The D1/D2 checker's rule, stated over a record: required fields present."""
    return all(record.get(field) not in (None, "") for field in FIELDS)


@dataclass(frozen=True)
class Decisions:
    """One verifier's decisions scored against independently held ground truth."""

    label: str
    true_accept: int
    false_accept: int
    true_reject: int
    false_reject: int

    @property
    def false_accept_rate(self) -> float:
        wrong = self.false_accept + self.true_reject
        return self.false_accept / wrong if wrong else 0.0

    @property
    def false_reject_rate(self) -> float:
        correct = self.true_accept + self.false_reject
        return self.false_reject / correct if correct else 0.0


def evaluate(
    label: str,
    accepts: Sequence[bool],
    states: Sequence[ResultState],
) -> Decisions:
    """Accepting anything not independently scored CORRECT is a false accept."""
    pairs = list(zip(accepts, states, strict=True))
    return Decisions(
        label=label,
        true_accept=sum(a and s is ResultState.CORRECT for a, s in pairs),
        false_accept=sum(a and s is not ResultState.CORRECT for a, s in pairs),
        true_reject=sum(not a and s is not ResultState.CORRECT for a, s in pairs),
        false_reject=sum(not a and s is ResultState.CORRECT for a, s in pairs),
    )


def cheap_extractions(
    base_url: str, tasks: Sequence[Task]
) -> tuple[list[dict[str, object]], list[tuple[Candidate, ...]], list[ResultState]]:
    """HTTP extraction, its candidate evidence, and its independent score."""
    records, candidates, states = [], [], []
    for task in tasks:
        extraction = extract_product(fetch(f"{base_url}{task.path}").html)
        records.append(extraction.record)
        candidates.append(extraction.candidates)
        states.append(score(extraction, task))
    return records, candidates, states


def reference_extractions(base_url: str) -> list[dict[str, object]]:
    """Previously verified labels: correct HTTP extractions of the reference pages."""
    records = []
    for path in REFERENCE_PATHS:
        record = extract_product(fetch(f"{base_url}{path}").html).record
        if any(record.get(field) is None for field in FIELDS):
            raise ValueError(f"reference page {path} did not extract a complete record")
        records.append(record)
    return records


@dataclass(frozen=True)
class Experiment:
    naive: Decisions
    rapture: dict[str, list[tuple[float, Decisions]]]
    stale_price_decisions: list[tuple[str, str, object, ResultState, bool, bool]]
    arm_e: Decisions
    # One row per HTTP record: task, state, E decision, and the conflicts it saw.
    e_traces: list[tuple[str, ResultState, evidence.Trace]]
    verifiers: dict[str, RaptureVerifier]
    # How many of its own verified labels each configuration accepts, per threshold.
    # Without this the false-reject column cannot be interpreted.
    self_acceptance: dict[str, list[tuple[float, int, int]]]


def run() -> Experiment:
    tasks = load_tasks(GROUND_TRUTH_PATH)
    with serve_fixtures() as base_url:
        reference = reference_extractions(base_url)
        records, candidates, states = cheap_extractions(base_url, tasks)

    naive = evaluate("naive", [naive_accepts(record) for record in records], states)
    e_decisions = [
        evidence.verify(record, candidate, FIELDS)
        for record, candidate in zip(records, candidates, strict=True)
    ]
    arm_e = evaluate("E", [d is evidence.Decision.ACCEPT for d in e_decisions], states)

    rapture: dict[str, list[tuple[float, Decisions]]] = {}
    verifiers: dict[str, RaptureVerifier] = {}
    for name, features, combine in CONFIGURATIONS:
        verifier = fit(reference, fields=FIELDS, features=features, combine=combine)
        verifiers[name] = verifier
        rapture[name] = [
            (
                tau,
                evaluate(
                    f"{name}@{tau}", [verifier.accepts(record, tau) for record in records], states
                ),
            )
            for tau in THRESHOLDS
        ]

    stale = [
        (
            task.task_id,
            name,
            record["price"] if isinstance(record.get("price"), int) else None,
            state,
            naive_accepts(record),
            verifiers[name].accepts(record, 0.5),
        )
        for task, record, state in zip(tasks, records, states, strict=True)
        if task.task_id in {"stale-html-price", "conflicting-prices", "stale-hydration-overwrite"}
        for name, _, _ in CONFIGURATIONS
    ]
    self_acceptance = {
        name: [
            (tau, sum(verifiers[name].accepts(record, tau) for record in reference), len(reference))
            for tau in THRESHOLDS
        ]
        for name, _, _ in CONFIGURATIONS
    }
    e_traces = [
        (task.task_id, state, evidence.Trace.of(record, candidate, FIELDS))
        for task, record, candidate, state in zip(tasks, records, candidates, states, strict=True)
    ]
    return Experiment(
        naive=naive,
        arm_e=arm_e,
        e_traces=e_traces,
        rapture=rapture,
        stale_price_decisions=stale,
        verifiers=verifiers,
        self_acceptance=self_acceptance,
    )


def _row(decisions: Decisions) -> str:
    return (
        f"TA={decisions.true_accept:2} FA={decisions.false_accept:2} "
        f"TR={decisions.true_reject:2} FR={decisions.false_reject:2}  "
        f"false-accept={decisions.false_accept_rate:.2f} "
        f"false-reject={decisions.false_reject_rate:.2f}"
    )


def format_experiment(experiment: Experiment) -> str:
    lines = [
        "CrawlBench v0.3 — arm E0 (RAPTURE-style verification, Kushmerick AAAI-99)",
        f"Reference labels: {len(REFERENCE_PATHS)}  Evaluated on cheap (HTTP) extractions",
        "",
        f"  naive (required fields)      {_row(experiment.naive)}",
        f"  E    (cross-source conflict) {_row(experiment.arm_e)}",
        "",
    ]
    for name, frontier in experiment.rapture.items():
        lines.append(f"  E0 {name}")
        self_accept = {tau: (n, total) for tau, n, total in experiment.self_acceptance[name]}
        for tau, decisions in frontier:
            accepted, total = self_accept[tau]
            lines.append(f"    tau={tau:<5} {_row(decisions)}  self-accept={accepted}/{total}")
        lines.append("")

    lines.append("  Arm E decisions on every non-CORRECT HTTP record:")
    for task_id, state, trace in experiment.e_traces:
        if state is not ResultState.CORRECT:
            lines.append(
                f"    {task_id:26} {state:14} {trace.decision:18} conflicts={trace.conflicts}"
            )
    lines.append("")
    lines.append("  Arm E rejections of CORRECT HTTP records:")
    rejected = [
        (t, tr)
        for t, s_, tr in experiment.e_traces
        if s_ is ResultState.CORRECT and tr.decision is not evidence.Decision.ACCEPT
    ]
    for task_id, trace in rejected or []:
        lines.append(f"    {task_id:26} {trace.decision:18} conflicts={trace.conflicts}")
    if not rejected:
        lines.append("    (none)")
    lines.append("")
    lines.append("  Stale-but-plausible fixtures at tau=0.5:")
    for task_id, config, price, state, naive_ok, rapture_ok in experiment.stale_price_decisions:
        lines.append(
            f"    {task_id:26} {config:26} price={price} {state:14} "
            f"naive={'accept' if naive_ok else 'reject'} "
            f"E0={'accept' if rapture_ok else 'reject'}"
        )
    return "\n".join(lines)
