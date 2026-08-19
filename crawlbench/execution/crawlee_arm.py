"""Crawlee adaptive arms C, D1, and D2 inside the CrawlBench harness.

The three arms are one code path differing only in the `(result_checker,
result_comparator)` pair handed to Crawlee, because that pair is the entire policy
under test. Extraction and scoring are the same functions the HTTP and Playwright
arms use.
"""

from __future__ import annotations

import os
import random
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any

from bs4 import BeautifulSoup, Tag
from crawlee._types import RequestHandlerRunResult
from crawlee.configuration import Configuration
from crawlee.crawlers import AdaptivePlaywrightCrawler, AdaptivePlaywrightCrawlingContext
from crawlee.crawlers._adaptive_playwright._adaptive_playwright_crawling_context import (
    AdaptiveContextError,
)
from crawlee.crawlers._adaptive_playwright._rendering_type_predictor import (
    DefaultRenderingTypePredictor,
)
from crawlee.crawlers._adaptive_playwright._result_comparator import push_data_only_comparator

from crawlbench.execution.playwright import READY_FLAG, READY_TIMEOUT_MS
from crawlbench.extraction import extract_product
from crawlbench.models import BenchmarkRecord, ExecutionMode, Extraction, ResultState, Task
from crawlbench.scoring import score

REQUIRED_FIELDS = ("name", "price", "currency")

ResultChecker = Callable[[RequestHandlerRunResult], bool]
ResultComparator = Callable[[RequestHandlerRunResult, RequestHandlerRunResult], bool]


def naive_checker(result: RequestHandlerRunResult) -> bool:
    """Required fields present and non-empty. D1 and D2 share this exact function."""
    if not result.push_data_calls:
        return False

    for call in result.push_data_calls:
        data = call["data"]
        items: Sequence[Mapping[str, Any]] = [data] if isinstance(data, Mapping) else data
        for item in items:
            if any(item.get(field) in (None, "") for field in REQUIRED_FIELDS):
                return False
    return True


# C takes Crawlee's defaults. D1 supplies only the checker, which is what silently
# replaces cross-mode comparison (CONFIRMATION-PASS.md §4a). D2 supplies the same
# checker plus the comparator Crawlee would otherwise have used.
def _launch_options() -> dict[str, Any]:
    """Crawlee launches a *persistent* browser context, which the Chromium sandbox refuses
    inside unprivileged CI containers — `launch_persistent_context` closes immediately and
    every request fails with NoResultCommitted. Our own Playwright arm is unaffected because
    it uses an ordinary launch.

    Disabling the sandbox is the documented workaround for that environment and is applied
    only there, so local and benchmark-of-record runs keep the default sandbox.
    """
    if os.environ.get("CI"):
        return {"args": ["--no-sandbox", "--disable-dev-shm-usage"]}
    return {}


ARM_POLICIES: dict[ExecutionMode, tuple[ResultChecker | None, ResultComparator | None]] = {
    ExecutionMode.CRAWLEE_C: (None, None),
    ExecutionMode.CRAWLEE_D1: (naive_checker, None),
    ExecutionMode.CRAWLEE_D2: (naive_checker, push_data_only_comparator),
}


@dataclass(frozen=True)
class RegimeContext:
    """Which predictor history a result was measured under.

    A Crawlee result is not interpretable without this, so it travels with the run
    and is written onto every record.
    """

    regime: str
    predictor_state_context: str
    repetition: int = 0


@dataclass(frozen=True)
class AdaptiveRun:
    """One arm, one regime, one repetition."""

    arm: ExecutionMode
    context: RegimeContext
    records: tuple[BenchmarkRecord, ...]
    # Handler invocations observed by our own handler. During a detection request
    # both sub-crawlers run it, so these count executions, not committed results.
    http_handler_runs: int
    browser_handler_runs: int
    # Crawlee's own counters, authoritative for the run.
    reported_http_runs: int
    reported_browser_runs: int
    mispredictions: int
    wall_time_seconds: float


async def run_adaptive_arm(  # noqa: PLR0913 - independent experiment coordinates.
    *,
    arm: ExecutionMode,
    crawl_tasks: Sequence[Task],
    scored_tasks: Sequence[Task],
    base_url: str,
    storage_dir: Path,
    seed: int,
    context: RegimeContext,
) -> AdaptiveRun:
    """Crawl `crawl_tasks` in the given order, then score `scored_tasks`.

    `crawl_tasks` and `scored_tasks` differ only in the transfer regime, where the
    family pages are crawled to train the predictor but only the unseen-template
    fixtures are scored.
    """
    # Crawlee samples `random()` to decide detection, so the run is only reproducible
    # if the global module state is seeded. There is no per-crawler seed hook.
    random.seed(seed)

    checker, comparator = ARM_POLICIES[arm]
    by_url = {f"{base_url}{task.path}": task for task in crawl_tasks}
    extracted: dict[str, dict[str, Any]] = {}
    handler_runs: list[tuple[str, bool]] = []

    crawler = AdaptivePlaywrightCrawler.with_beautifulsoup_static_parser(
        rendering_type_predictor=DefaultRenderingTypePredictor(),
        result_checker=checker,
        result_comparator=comparator,
        configuration=Configuration(storage_dir=str(storage_dir), purge_on_start=True),
        playwright_crawler_specific_kwargs={"browser_launch_options": _launch_options()},
    )

    @crawler.router.default_handler
    async def handler(crawl_context: AdaptivePlaywrightCrawlingContext[BeautifulSoup, Tag]) -> None:
        try:
            page = crawl_context.page
        except AdaptiveContextError:
            html = (await crawl_context.http_response.read()).decode("utf-8")
            browser_rendered = False
        else:
            # The same readiness contract the Playwright arm waits on, so neither arm
            # is timed against a half-rendered page.
            await page.wait_for_function(READY_FLAG, timeout=READY_TIMEOUT_MS)
            html = await page.content()
            browser_rendered = True

        task = by_url[crawl_context.request.url]
        handler_runs.append((task.task_id, browser_rendered))
        # Only the extracted record is pushed. Anything mode-dependent in this payload
        # would be fed straight into the comparator and manufacture a disagreement.
        await crawl_context.push_data({"task_id": task.task_id, **extract_product(html).record})

    start = perf_counter()
    await crawler.run([f"{base_url}{task.path}" for task in crawl_tasks])
    wall_time_seconds = perf_counter() - start

    for item in (await crawler.get_data()).items:
        record = dict(item)
        extracted[str(record.pop("task_id"))] = record

    state = crawler.statistics.state
    return AdaptiveRun(
        arm=arm,
        context=context,
        records=tuple(
            _score_task(
                task=task,
                arm=arm,
                context=context,
                record=extracted.get(task.task_id),
                handler_runs=handler_runs,
            )
            for task in scored_tasks
        ),
        http_handler_runs=sum(1 for _, rendered in handler_runs if not rendered),
        browser_handler_runs=sum(1 for _, rendered in handler_runs if rendered),
        reported_http_runs=state.http_only_request_handler_runs,
        reported_browser_runs=state.browser_request_handler_runs,
        mispredictions=state.rendering_type_mispredictions,
        wall_time_seconds=wall_time_seconds,
    )


def _score_task(
    *,
    task: Task,
    arm: ExecutionMode,
    context: RegimeContext,
    record: dict[str, Any] | None,
    handler_runs: Sequence[tuple[str, bool]],
) -> BenchmarkRecord:
    if record is None:
        result_state = ResultState.FAILED
        error_type = "NoResultCommitted"
    else:
        result_state = score(Extraction(record=record), task)
        error_type = None

    runs = [rendered for task_id, rendered in handler_runs if task_id == task.task_id]
    return BenchmarkRecord(
        task_id=task.task_id,
        arm=arm,
        result_state=result_state,
        # Crawlee owns scheduling, so there is no comparable per-task boundary here.
        wall_time_seconds=None,
        cpu_time_seconds=None,
        process_tree_rss_bytes=None,
        # Which of a detection request's two runs Crawlee committed is not exposed,
        # so this reports whether the browser ran for this task at all.
        browser_rendered=any(runs) if runs else None,
        extracted_record=record,
        expected_record=task.expected,
        error_type=error_type,
        bytes_transferred=None,
        regime=context.regime,
        predictor_state_context=context.predictor_state_context,
        repetition=context.repetition,
    )
