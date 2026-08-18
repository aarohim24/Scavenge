"""The three predictor regimes for the Crawlee arms.

An adaptive result means nothing without the predictor history that produced it, so
every regime declares what the predictor had already seen and in what order.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from crawlbench.benchmark import write_jsonl
from crawlbench.execution.crawlee_arm import (
    ARM_POLICIES,
    AdaptiveRun,
    RegimeContext,
    run_adaptive_arm,
)
from crawlbench.models import BenchmarkRecord, ResultState, Task, load_tasks
from fixtures.server import GROUND_TRUTH_PATH, serve_fixtures

# Canonical ordering is ground-truth file order. Crawlee learns online, so the order
# is part of the experiment and is declared rather than chosen per run.
REPETITIONS = 3
SEEDS = (11, 22, 33)


_FAMILY_PATH_SEGMENTS = 2


def is_family_task(task: Task) -> bool:
    """Family pages are `/<family>/<id>`; the v0.1 island fixtures are `/<name>`."""
    return task.path.count("/") == _FAMILY_PATH_SEGMENTS


@dataclass(frozen=True)
class RegimeResult:
    name: str
    runs: tuple[AdaptiveRun, ...]


async def run_regimes(
    base_url: str,
    *,
    tasks: Sequence[Task],
    storage_root: Path,
) -> list[RegimeResult]:
    islands = [task for task in tasks if not is_family_task(task)]
    families = [task for task in tasks if is_family_task(task)]

    regimes = [
        # R1: no useful URL-family knowledge.
        ("R1_COLD_UNSEEN", islands, islands, "fresh"),
        # R2: the predictor sees three URL families it can generalise within.
        ("R2_LEARNED_FAMILIES", families, families, "fresh"),
        # R3: families are crawled first, then the island fixtures are met for the
        # first time as previously unseen templates.
        ("R3_TRANSFER_UNSEEN", [*families, *islands], islands, "family_trained"),
    ]

    results = []
    for name, crawl_tasks, scored_tasks, state_context in regimes:
        # Crawlee learns online, so order is an experimental variable, not a detail.
        # Both orderings are reported because they do not agree.
        for ordering, ordered in (("canonical", crawl_tasks), ("reversed", crawl_tasks[::-1])):
            regime_name = f"{name}/{ordering}"
            runs = []
            for arm in ARM_POLICIES:
                for repetition, seed in enumerate(SEEDS[:REPETITIONS]):
                    with TemporaryDirectory(dir=storage_root) as storage_dir:
                        runs.append(
                            await run_adaptive_arm(
                                arm=arm,
                                crawl_tasks=ordered,
                                scored_tasks=scored_tasks,
                                base_url=base_url,
                                storage_dir=Path(storage_dir),
                                seed=seed,
                                context=RegimeContext(
                                    regime=regime_name,
                                    predictor_state_context=state_context,
                                    repetition=repetition,
                                ),
                            )
                        )
            results.append(RegimeResult(name=regime_name, runs=tuple(runs)))
    return results


def run() -> tuple[Path, list[RegimeResult]]:
    tasks = load_tasks(GROUND_TRUTH_PATH)
    results_dir = Path("results")
    results_dir.mkdir(parents=True, exist_ok=True)
    run_id = uuid4().hex

    async def _main() -> list[RegimeResult]:
        with serve_fixtures() as base_url, TemporaryDirectory() as storage_root:
            return await run_regimes(base_url, tasks=tasks, storage_root=Path(storage_root))

    results = asyncio.run(_main())

    records = [record for regime in results for run_ in regime.runs for record in run_.records]
    jsonl_path = results_dir / f"{run_id}.adaptive.jsonl"
    write_jsonl(records, jsonl_path)
    diagnostics = [
        {
            **{key: value for key, value in asdict(run_).items() if key != "records"},
        }
        for regime in results
        for run_ in regime.runs
    ]
    (results_dir / f"{run_id}.adaptive.meta.json").write_text(
        json.dumps(diagnostics, indent=2) + "\n", encoding="utf-8"
    )
    return jsonl_path, results


def count(records: Sequence[BenchmarkRecord], state: ResultState) -> int:
    return sum(record.result_state is state for record in records)


def detection_requests(run_: AdaptiveRun) -> int:
    """Requests that paid for both a browser and an HTTP run so the predictor could learn.

    Crawlee counts a detection request as a browser run, so the extra static passes
    are the difference between the static handler runs we observed and the static
    runs Crawlee committed.
    """
    return run_.http_handler_runs - run_.reported_http_runs


def _span(values: Sequence[int]) -> str:
    low, high = min(values), max(values)
    return str(low) if low == high else f"{low}-{high}"


def format_regimes(jsonl_path: Path, results: Sequence[RegimeResult]) -> str:
    lines = [
        "CrawlBench v0.2 — Crawlee adaptive arms",
        f"{REPETITIONS} repetitions per cell, seeds {SEEDS[:REPETITIONS]}; ranges are min-max.",
        "",
    ]
    for regime in results:
        lines += [regime.name, "-" * len(regime.name)]
        for arm in ARM_POLICIES:
            runs = [run_ for run_ in regime.runs if run_.arm is arm]
            false_success = [count(r.records, ResultState.FALSE_SUCCESS) for r in runs]
            lines.append(
                f"  {arm:11} tasks={len(runs[0].records):2}  "
                f"correct={_span([count(r.records, ResultState.CORRECT) for r in runs])} "
                f"false_success={_span(false_success)} "
                f"failed={_span([count(r.records, ResultState.FAILED) for r in runs])}  "
                f"http_runs={_span([r.reported_http_runs for r in runs])} "
                f"browser_runs={_span([r.reported_browser_runs for r in runs])} "
                f"detections={_span([detection_requests(r) for r in runs])} "
                f"mispredictions={_span([r.mispredictions for r in runs])}"
            )
        lines.append("")
    lines.append(f"Raw results: {jsonl_path}")
    return "\n".join(lines)
