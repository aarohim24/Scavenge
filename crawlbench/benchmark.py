"""Benchmark execution, scoring, measurement, and result storage."""

from __future__ import annotations

import json
import platform
import sys
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from importlib.metadata import version
from pathlib import Path
from statistics import median
from time import perf_counter
from typing import Any, Protocol
from uuid import uuid4

from crawlbench.execution.http import fetch as fetch_http
from crawlbench.execution.playwright import WarmPlaywrightSession, launch_warm_playwright_session
from crawlbench.extraction import extract_product
from crawlbench.measurement import snapshot_process_tree
from crawlbench.models import (
    BenchmarkRecord,
    ExecutionMode,
    ResultState,
    RunMetadata,
    Task,
    load_tasks,
)
from crawlbench.scoring import score
from fixtures.server import GROUND_TRUTH_PATH, serve_fixtures


class BrowserSessionFactory(Protocol):
    def __call__(self) -> Any: ...


@dataclass(frozen=True)
class RunResult:
    run_id: str
    records: tuple[BenchmarkRecord, ...]
    metadata: RunMetadata
    jsonl_path: Path
    metadata_path: Path


@dataclass(frozen=True)
class ArmSummary:
    correct: int
    false_success: int
    failed: int
    p50_wall_time_seconds: float


@dataclass(frozen=True)
class Summary:
    task_count: int
    http: ArmSummary
    playwright: ArmSummary


def run() -> RunResult:
    results_dir = Path("results")
    results_dir.mkdir(parents=True, exist_ok=True)
    run_id = uuid4().hex
    tasks = load_tasks(GROUND_TRUTH_PATH)
    with serve_fixtures() as base_url:
        return run_benchmark(
            tasks=tasks,
            base_url=base_url,
            results_dir=results_dir,
            run_id=run_id,
            browser_factory=launch_warm_playwright_session,
        )


def run_benchmark(
    *,
    tasks: Sequence[Task],
    base_url: str,
    results_dir: Path,
    run_id: str,
    browser_factory: BrowserSessionFactory,
) -> RunResult:
    http_records = run_http_arm(tasks, base_url)

    browser_startup_seconds: float | None = None
    chromium_version = "unknown"
    playwright_version = version("playwright")
    with browser_factory() as session:
        browser_startup_seconds = session.startup_seconds
        chromium_version = session.chromium_version
        playwright_version = session.playwright_version
        playwright_records = run_playwright_arm(tasks, base_url, session)

    records = (*http_records, *playwright_records)
    metadata = collect_run_metadata(
        run_id=run_id,
        browser_startup_seconds=browser_startup_seconds,
        playwright_version=playwright_version,
        chromium_version=chromium_version,
    )
    jsonl_path = results_dir / f"{run_id}.jsonl"
    metadata_path = results_dir / f"{run_id}.meta.json"
    write_jsonl(records, jsonl_path)
    metadata_path.write_text(json.dumps(asdict(metadata), indent=2) + "\n", encoding="utf-8")
    return RunResult(
        run_id=run_id,
        records=records,
        metadata=metadata,
        jsonl_path=jsonl_path,
        metadata_path=metadata_path,
    )


def run_http_arm(tasks: Sequence[Task], base_url: str) -> list[BenchmarkRecord]:
    return [run_task(task, ExecutionMode.HTTP, fetch_http, base_url) for task in tasks]


def run_playwright_arm(
    tasks: Sequence[Task],
    base_url: str,
    session: WarmPlaywrightSession,
) -> list[BenchmarkRecord]:
    return [run_task(task, ExecutionMode.PLAYWRIGHT, session.fetch, base_url) for task in tasks]


def run_task(
    task: Task,
    arm: ExecutionMode,
    fetch_document: Callable[[str], Any],
    base_url: str,
) -> BenchmarkRecord:
    start_wall = perf_counter()
    start_snapshot = snapshot_process_tree()
    extracted_record: dict[str, Any] | None = None
    error_type: str | None = None
    result_state = ResultState.FAILED
    bytes_transferred: int | None = None

    try:
        document = fetch_document(f"{base_url}{task.path}")
        bytes_transferred = document.bytes_transferred
        extraction = extract_product(document.html)
        extracted_record = extraction.record
        result_state = score(extraction, task)
    except Exception as exc:  # noqa: BLE001 - benchmark records failures explicitly.
        error_type = exc.__class__.__name__

    end_snapshot = snapshot_process_tree()
    wall_time_seconds = perf_counter() - start_wall
    cpu_time_seconds = max(0.0, end_snapshot.cpu_time_seconds - start_snapshot.cpu_time_seconds)
    process_tree_rss_bytes = end_snapshot.rss_bytes
    return BenchmarkRecord(
        task_id=task.task_id,
        arm=arm,
        result_state=result_state,
        wall_time_seconds=wall_time_seconds,
        cpu_time_seconds=cpu_time_seconds,
        process_tree_rss_bytes=process_tree_rss_bytes,
        browser_rendered=arm is ExecutionMode.PLAYWRIGHT,
        extracted_record=extracted_record,
        expected_record=task.expected,
        error_type=error_type,
        bytes_transferred=bytes_transferred,
    )


def summarize_records(records: Sequence[BenchmarkRecord]) -> Summary:
    http_records = [record for record in records if record.arm is ExecutionMode.HTTP]
    playwright_records = [record for record in records if record.arm is ExecutionMode.PLAYWRIGHT]
    return Summary(
        task_count=len({record.task_id for record in records}),
        http=_summarize_arm(http_records),
        playwright=_summarize_arm(playwright_records),
    )


def _summarize_arm(records: Sequence[BenchmarkRecord]) -> ArmSummary:
    return ArmSummary(
        correct=sum(record.result_state is ResultState.CORRECT for record in records),
        false_success=sum(record.result_state is ResultState.FALSE_SUCCESS for record in records),
        failed=sum(record.result_state is ResultState.FAILED for record in records),
        p50_wall_time_seconds=median(
            record.wall_time_seconds for record in records if record.wall_time_seconds is not None
        ),
    )


def write_jsonl(records: Sequence[BenchmarkRecord], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(asdict(record), ensure_ascii=True) + "\n")


def collect_run_metadata(
    *,
    run_id: str,
    browser_startup_seconds: float | None,
    playwright_version: str,
    chromium_version: str,
) -> RunMetadata:
    return RunMetadata(
        run_id=run_id,
        python_version=sys.version.split()[0],
        platform=platform.platform(),
        architecture=platform.machine(),
        dependencies={
            "httpx": version("httpx"),
            "playwright": playwright_version,
            "psutil": version("psutil"),
            "selectolax": version("selectolax"),
        },
        playwright_version=playwright_version,
        chromium_version=chromium_version,
        browser_startup_seconds=browser_startup_seconds,
    )


def format_summary(result: RunResult) -> str:
    summary = summarize_records(result.records)
    browser_startup = (
        f"{result.metadata.browser_startup_seconds:.4f}s"
        if result.metadata.browser_startup_seconds is not None
        else "unsupported"
    )
    return "\n".join(
        [
            "CrawlBench v0.1",
            f"Tasks: {summary.task_count}",
            "",
            "HTTP",
            f"Correct:        {summary.http.correct}",
            f"False success:  {summary.http.false_success}",
            f"Failed:         {summary.http.failed}",
            f"p50 wall time:  {summary.http.p50_wall_time_seconds:.4f}s",
            "",
            "Playwright",
            f"Correct:        {summary.playwright.correct}",
            f"False success:  {summary.playwright.false_success}",
            f"Failed:         {summary.playwright.failed}",
            f"p50 wall time:  {summary.playwright.p50_wall_time_seconds:.4f}s",
            "",
            f"Browser startup: {browser_startup}",
            "",
            f"Raw results: {result.jsonl_path}",
            f"Metadata: {result.metadata_path}",
        ]
    )
