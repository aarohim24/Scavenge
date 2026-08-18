"""The v0.1 vertical slice: fixture -> HTTP/Playwright -> extract -> score."""

from __future__ import annotations

import ast
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

import pytest

import crawlbench.scoring
from crawlbench.benchmark import (
    collect_run_metadata,
    run_benchmark,
    run_http_arm,
    run_playwright_arm,
    run_task,
    summarize_records,
    write_jsonl,
)
from crawlbench.execution.http import fetch
from crawlbench.execution.playwright import launch_warm_playwright_session
from crawlbench.extraction import extract_product
from crawlbench.models import ExecutionMode, Extraction, ResultState, Task, load_tasks
from crawlbench.scoring import missing_required_fields, score
from fixtures.server import GROUND_TRUTH_PATH, serve_fixtures

TASKS = load_tasks(GROUND_TRUTH_PATH)
TASKS_BY_ID = {task.task_id: task for task in TASKS}
TASK_COUNT = 2
HTTP_CORRECT = 1
HTTP_FALSE_SUCCESS = 1
PLAYWRIGHT_CORRECT = 2
JSONL_LINES = 4
STALE_HYDRATION_PRICE = 2999
HTTP_OK = 200


@pytest.fixture(scope="module")
def base_url() -> Iterator[str]:
    with serve_fixtures() as url:
        yield url


def test_every_task_serves_a_page(base_url: str) -> None:
    """Island fixtures are files; family pages render from templates. Both must serve."""
    for task in TASKS:
        document = fetch(f"{base_url}{task.path}")
        assert document.status_code == HTTP_OK, f"task {task.task_id} did not serve"
        assert document.html.strip(), f"task {task.task_id} served an empty page"


def test_static_product_over_http_is_correct(base_url: str) -> None:
    task = TASKS_BY_ID["static-product"]

    document = fetch(f"{base_url}{task.path}")
    extraction = extract_product(document.html)

    assert document.execution_mode is ExecutionMode.HTTP
    assert document.bytes_transferred is not None
    assert document.bytes_transferred > 0
    assert extraction.record == task.expected
    assert score(extraction, task) is ResultState.CORRECT


def test_jsonld_product_over_http_is_correct(base_url: str) -> None:
    task = TASKS_BY_ID["jsonld-product"]

    document = fetch(f"{base_url}{task.path}")
    extraction = extract_product(document.html)

    assert score(extraction, task) is ResultState.CORRECT


def test_hydration_product_over_http_is_correct(base_url: str) -> None:
    """The embedded JSON payload is readable without a browser, so HTTP must suffice."""
    task = TASKS_BY_ID["hydration-product"]

    document = fetch(f"{base_url}{task.path}")
    extraction = extract_product(document.html)

    assert score(extraction, task) is ResultState.CORRECT


def test_stale_price_http_is_false_success(base_url: str) -> None:
    task = TASKS_BY_ID["stale-html-price"]

    document = fetch(f"{base_url}{task.path}")
    extraction = extract_product(document.html)

    assert extraction.record == {"name": "Stale Price Product", "price": 2999, "currency": "INR"}
    assert score(extraction, task) is ResultState.FALSE_SUCCESS


def test_stale_price_playwright_is_correct(base_url: str) -> None:
    task = TASKS_BY_ID["stale-html-price"]

    with launch_warm_playwright_session() as session:
        document = session.fetch(f"{base_url}{task.path}")

    extraction = extract_product(document.html)

    assert document.execution_mode is ExecutionMode.PLAYWRIGHT
    assert extraction.record == task.expected
    assert score(extraction, task) is ResultState.CORRECT


def test_client_rendered_fixture_needs_browser(base_url: str) -> None:
    task = TASKS_BY_ID["client-rendered-product"]

    http_document = fetch(f"{base_url}{task.path}")
    http_extraction = extract_product(http_document.html)

    with launch_warm_playwright_session() as session:
        playwright_document = session.fetch(f"{base_url}{task.path}")

    playwright_extraction = extract_product(playwright_document.html)

    assert score(http_extraction, task) is ResultState.FAILED
    assert score(playwright_extraction, task) is ResultState.CORRECT


def test_failed_client_fetch_is_correct_over_http_and_failed_under_playwright(
    base_url: str,
) -> None:
    """Executing the page destroys a record the raw HTML already carried."""
    task = TASKS_BY_ID["failed-client-fetch"]

    http_document = fetch(f"{base_url}{task.path}")
    http_extraction = extract_product(http_document.html)

    with launch_warm_playwright_session() as session:
        playwright_document = session.fetch(f"{base_url}{task.path}")

    playwright_extraction = extract_product(playwright_document.html)

    assert http_extraction.record == task.expected
    assert score(http_extraction, task) is ResultState.CORRECT
    assert missing_required_fields(playwright_extraction, task) == ("price",)
    assert score(playwright_extraction, task) is ResultState.FAILED


def test_stale_hydration_overwrite_is_false_success_under_playwright(base_url: str) -> None:
    """FALSE_SUCCESS is a property of the record, not of the arm that produced it."""
    task = TASKS_BY_ID["stale-hydration-overwrite"]

    http_document = fetch(f"{base_url}{task.path}")
    http_extraction = extract_product(http_document.html)

    with launch_warm_playwright_session() as session:
        playwright_document = session.fetch(f"{base_url}{task.path}")

    playwright_extraction = extract_product(playwright_document.html)

    assert score(http_extraction, task) is ResultState.CORRECT
    assert playwright_extraction.record["price"] == STALE_HYDRATION_PRICE
    assert score(playwright_extraction, task) is ResultState.FALSE_SUCCESS


def test_missing_required_field_is_failed() -> None:
    task = TASKS_BY_ID["static-product"]
    extraction = Extraction(record={"name": "Example Product", "price": 1999})

    assert missing_required_fields(extraction, task) == ("currency",)
    assert score(extraction, task) is ResultState.FAILED


def test_none_valued_field_counts_as_missing() -> None:
    task = TASKS_BY_ID["static-product"]
    extraction = Extraction(record={"name": "Example Product", "price": None, "currency": "INR"})

    assert score(extraction, task) is ResultState.FAILED


def test_missing_field_fixture_scores_failed_under_both_arms(base_url: str) -> None:
    task = TASKS_BY_ID["missing-field"]

    http_document = fetch(f"{base_url}{task.path}")
    http_extraction = extract_product(http_document.html)

    with launch_warm_playwright_session() as session:
        playwright_document = session.fetch(f"{base_url}{task.path}")

    playwright_extraction = extract_product(playwright_document.html)

    assert score(http_extraction, task) is ResultState.FAILED
    assert score(playwright_extraction, task) is ResultState.FAILED


def test_complete_but_wrong_record_is_false_success() -> None:
    """The stale-price problem in miniature: plausible, complete, wrong."""
    task = TASKS_BY_ID["static-product"]
    extraction = Extraction(record={"name": "Example Product", "price": 2999, "currency": "INR"})

    assert missing_required_fields(extraction, task) == ()
    assert score(extraction, task) is ResultState.FALSE_SUCCESS


def test_scoring_cannot_consult_execution_mode() -> None:
    """Structural guard: ground truth must stay independent of how a page was fetched.

    Scoring that can see the execution mode (or a `Document`) is one refactor away
    from treating the browser arm as an oracle.
    """
    module = ast.parse(Path(crawlbench.scoring.__file__).read_text(encoding="utf-8"))
    imported = {
        alias.asname or alias.name
        for node in ast.walk(module)
        if isinstance(node, ast.ImportFrom | ast.Import)
        for alias in node.names
    }

    assert "ExecutionMode" not in imported
    assert "Document" not in imported


def test_http_and_playwright_share_the_same_result_schema(base_url: str) -> None:
    task = TASKS_BY_ID["static-product"]

    http_record = run_task(task, ExecutionMode.HTTP, fetch, base_url)
    with launch_warm_playwright_session() as session:
        playwright_record = run_task(task, ExecutionMode.PLAYWRIGHT, session.fetch, base_url)

    assert http_record.__dict__.keys() == playwright_record.__dict__.keys()


def test_jsonl_records_reconstruct_summary_and_metadata(base_url: str, tmp_path: Path) -> None:
    tasks = (TASKS_BY_ID["static-product"], TASKS_BY_ID["stale-html-price"])
    http_records = run_http_arm(tasks, base_url)
    with launch_warm_playwright_session() as session:
        playwright_records = run_playwright_arm(tasks, base_url, session)

    records = [*http_records, *playwright_records]
    jsonl_path = tmp_path / "run.jsonl"
    write_jsonl(records, jsonl_path)
    metadata = collect_run_metadata(
        run_id="run-1",
        browser_startup_seconds=0.1,
        playwright_version="1.62.0",
        chromium_version="151.0.7922.34",
    )
    summary = summarize_records(records)

    assert summary.task_count == TASK_COUNT
    assert summary.http.correct == HTTP_CORRECT
    assert summary.http.false_success == HTTP_FALSE_SUCCESS
    assert summary.playwright.correct == PLAYWRIGHT_CORRECT
    assert jsonl_path.read_text(encoding="utf-8").count("\n") == JSONL_LINES
    assert metadata.browser_startup_seconds == pytest.approx(0.1)


@dataclass
class _FakeSession:
    startup_seconds: float = 0.1
    playwright_version: str = "1.62.0"
    chromium_version: str = "151.0.7922.34"
    closed: bool = False
    calls: int = 0

    def fetch(self, url: str) -> object:
        self.calls += 1
        if self.calls > 1:
            raise RuntimeError("boom")
        return type(
            "FakeDocument",
            (),
            {
                "html": (
                    "<!doctype html><html><body><h1 class='product-title'>Example Product</h1>"
                    "<span class='price' data-currency='INR'>₹1,999</span>"
                    "<script>window.__CRAWLBENCH_READY = true;</script></body></html>"
                ),
                "bytes_transferred": None,
                "execution_mode": ExecutionMode.PLAYWRIGHT,
                "status_code": 200,
                "url": url,
            },
        )()


@contextmanager
def _fake_session_factory() -> Iterator[_FakeSession]:
    session = _FakeSession()
    try:
        yield session
    finally:
        session.closed = True


def test_browser_session_is_reused_and_closed_after_error(base_url: str, tmp_path: Path) -> None:
    tasks = (TASKS_BY_ID["static-product"], TASKS_BY_ID["stale-html-price"])
    result = run_benchmark(
        tasks=tasks,
        base_url=base_url,
        results_dir=tmp_path,
        run_id="demo-run",
        browser_factory=_fake_session_factory,
    )

    playwright_records = [
        record for record in result.records if record.arm is ExecutionMode.PLAYWRIGHT
    ]
    assert len(playwright_records) == TASK_COUNT
    assert playwright_records[0].result_state is ResultState.CORRECT
    assert playwright_records[1].result_state is ResultState.FAILED
    assert result.metadata.browser_startup_seconds == pytest.approx(0.1)
    assert result.metadata_path.is_file()


def test_warm_browser_is_reused_across_tasks_and_closed_afterwards(base_url: str) -> None:
    """One Chromium process must serve the whole run, then shut down."""
    tasks = (TASKS_BY_ID["static-product"], TASKS_BY_ID["stale-html-price"])

    with launch_warm_playwright_session() as session:
        browser = session.browser
        records = run_playwright_arm(tasks, base_url, session)
        assert browser.is_connected()

    assert len(records) == TASK_COUNT
    assert all(record.result_state is ResultState.CORRECT for record in records)
    assert not browser.is_connected()


def test_wall_time_is_non_negative_and_bytes_are_explicitly_unsupported(base_url: str) -> None:
    """Playwright cannot report transferred bytes comparably, so it reports None, not 0."""
    task = TASKS_BY_ID["static-product"]

    http_record = run_task(task, ExecutionMode.HTTP, fetch, base_url)
    with launch_warm_playwright_session() as session:
        playwright_record = run_task(task, ExecutionMode.PLAYWRIGHT, session.fetch, base_url)

    for record in (http_record, playwright_record):
        assert record.wall_time_seconds is not None
        assert record.cpu_time_seconds is not None
        assert record.wall_time_seconds >= 0
        assert record.cpu_time_seconds >= 0
    assert http_record.bytes_transferred is not None
    assert playwright_record.bytes_transferred is None


def test_ground_truth_rejects_fields_it_does_not_define() -> None:
    with pytest.raises(ValueError, match="required fields absent from ground truth"):
        Task(
            task_id="broken",
            path="/broken",
            required_fields=("name", "price"),
            expected={"name": "Example Product"},
        )
