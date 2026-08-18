"""The Crawlee arms: policy wiring, regimes, and result records."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from pathlib import Path
from typing import Any, cast

import psutil
import pytest
from crawlee._types import PushDataFunctionCall, RequestHandlerRunResult
from crawlee.crawlers._adaptive_playwright._result_comparator import (
    create_default_comparator,
    push_data_only_comparator,
)

from crawlbench.adaptive import detection_requests, is_family_task
from crawlbench.execution.crawlee_arm import (
    ARM_POLICIES,
    RegimeContext,
    naive_checker,
    run_adaptive_arm,
)
from crawlbench.models import BenchmarkRecord, ExecutionMode, ResultState, load_tasks
from fixtures.server import GROUND_TRUTH_PATH, serve_fixtures

TASKS = load_tasks(GROUND_TRUTH_PATH)
TASKS_BY_ID = {task.task_id: task for task in TASKS}
FAMILY_TASK_COUNT = 9
DEALS_LIST_PRICE = 2599
DEALS_OFFER_PRICE = 1799


def _result(**record: Any) -> RequestHandlerRunResult:
    """A genuine `RequestHandlerRunResult`; these policies never touch its store getter."""
    result = RequestHandlerRunResult(key_value_store_getter=cast(Any, None))
    if record:
        result.push_data_calls.append(
            PushDataFunctionCall(
                data=record, dataset_id=None, dataset_name=None, dataset_alias=None
            )
        )
    return result


@pytest.fixture(scope="module")
def base_url() -> Iterator[str]:
    with serve_fixtures() as url:
        yield url


def test_arm_c_supplies_neither_policy() -> None:
    """C must be Crawlee's defaults, not our approximation of them."""
    assert ARM_POLICIES[ExecutionMode.CRAWLEE_C] == (None, None)


def test_d1_and_d2_share_one_checker_and_differ_only_in_the_comparator() -> None:
    d1_checker, d1_comparator = ARM_POLICIES[ExecutionMode.CRAWLEE_D1]
    d2_checker, d2_comparator = ARM_POLICIES[ExecutionMode.CRAWLEE_D2]

    assert d1_checker is d2_checker is naive_checker
    assert d1_comparator is None
    assert d2_comparator is push_data_only_comparator


def test_naive_checker_requires_every_field() -> None:
    assert naive_checker(_result(name="A", price=1, currency="INR"))
    assert not naive_checker(_result(name="A", price=1))
    assert not naive_checker(_result())


def test_supplying_only_a_checker_replaces_cross_mode_comparison() -> None:
    """CONFIRMATION-PASS.md section 4a, reproduced against the installed Crawlee.

    D1's stale-but-complete static result and the browser's correct result disagree,
    yet the comparator Crawlee builds for a checker-only user calls them equivalent.
    """
    static = _result(name="Flash Hour Bundle", price=DEALS_LIST_PRICE, currency="INR")
    browser = _result(name="Flash Hour Bundle", price=DEALS_OFFER_PRICE, currency="INR")

    d1_comparator = create_default_comparator(naive_checker)

    assert d1_comparator(static, browser) is True
    assert push_data_only_comparator(static, browser) is False


def test_family_tasks_are_distinguished_by_path_shape() -> None:
    assert is_family_task(TASKS_BY_ID["products-101"])
    assert not is_family_task(TASKS_BY_ID["stale-html-price"])
    assert sum(is_family_task(task) for task in TASKS) == FAMILY_TASK_COUNT


def _run(arm: ExecutionMode, tasks: list[Any], base_url: str, tmp_path: Path) -> Any:
    return asyncio.run(
        run_adaptive_arm(
            arm=arm,
            crawl_tasks=tasks,
            scored_tasks=tasks,
            base_url=base_url,
            storage_dir=tmp_path,
            seed=11,
            context=RegimeContext(regime="TEST", predictor_state_context="fresh"),
        )
    )


def test_adaptive_run_records_carry_predictor_history(base_url: str, tmp_path: Path) -> None:
    """A Crawlee result without its predictor history is not a valid CrawlBench result."""
    tasks = [TASKS_BY_ID["products-101"], TASKS_BY_ID["products-102"]]

    run = _run(ExecutionMode.CRAWLEE_D2, tasks, base_url, tmp_path)

    assert len(run.records) == len(tasks)
    for record in run.records:
        assert record.arm is ExecutionMode.CRAWLEE_D2
        assert record.regime == "TEST"
        assert record.predictor_state_context == "fresh"
        assert record.result_state is ResultState.CORRECT
    # Same schema as the HTTP and Playwright arms, so one JSONL covers every arm.
    assert set(run.records[0].__dict__) == set(BenchmarkRecord.__dataclass_fields__)


def test_unsupported_metrics_are_absent_rather_than_invented(base_url: str, tmp_path: Path) -> None:
    """Crawlee owns scheduling, so per-task cost has no comparable boundary."""
    run = _run(ExecutionMode.CRAWLEE_C, [TASKS_BY_ID["products-101"]], base_url, tmp_path)

    record = run.records[0]
    assert record.wall_time_seconds is None
    assert record.cpu_time_seconds is None
    assert record.bytes_transferred is None
    assert run.wall_time_seconds >= 0


def test_detection_requests_pay_for_both_modes(base_url: str, tmp_path: Path) -> None:
    """The first request is always dual-rendered, so learning is never free."""
    tasks = [TASKS_BY_ID["products-101"], TASKS_BY_ID["products-102"]]

    run = _run(ExecutionMode.CRAWLEE_C, tasks, base_url, tmp_path)

    assert detection_requests(run) >= 1
    assert run.http_handler_runs + run.browser_handler_runs > len(tasks)
    # Crawlee's own counters must account for every task exactly once.
    assert run.reported_http_runs + run.reported_browser_runs == len(tasks)


def test_browser_processes_are_cleaned_up_after_a_run(base_url: str, tmp_path: Path) -> None:
    _run(ExecutionMode.CRAWLEE_C, [TASKS_BY_ID["listings-201"]], base_url, tmp_path)

    children = psutil.Process().children(recursive=True)
    assert not [child for child in children if "chrome" in child.name().lower()]


def test_scoring_is_the_same_path_used_by_the_http_arm(base_url: str, tmp_path: Path) -> None:
    """deals-303 ships a stale price; whichever mode commits it, scoring is unchanged."""
    run = _run(ExecutionMode.CRAWLEE_D1, [TASKS_BY_ID["deals-303"]], base_url, tmp_path)

    record = run.records[0]
    assert record.extracted_record is not None
    if record.extracted_record["price"] == DEALS_LIST_PRICE:
        assert record.result_state is ResultState.FALSE_SUCCESS
    else:
        assert record.result_state is ResultState.CORRECT
