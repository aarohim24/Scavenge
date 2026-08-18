"""Core data models shared by every benchmark arm.

Both HTTP and browser arms must produce the same `Document` and `Extraction`
types, so that scoring and measurement cannot accidentally treat one arm as
privileged.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any


class ResultState(StrEnum):
    """Outcome of one benchmark task under one arm.

    `FALSE_SUCCESS` exists because a complete, plausible, wrong record is the
    failure mode this benchmark was built to expose. It is never merged into
    `FAILED` and never reported as success.
    """

    CORRECT = "CORRECT"
    FALSE_SUCCESS = "FALSE_SUCCESS"
    FAILED = "FAILED"


class EvidenceSource(StrEnum):
    """Which channel of the cheap document a value came from.

    Two candidates count as independent only when these differ: two DOM selectors
    finding the same value are one observation, not two.
    """

    DOM = "DOM"
    ATTRIBUTE = "ATTRIBUTE"
    JSON_LD = "JSON_LD"
    EMBEDDED_JSON = "EMBEDDED_JSON"


class ExecutionMode(StrEnum):
    HTTP = "HTTP"
    PLAYWRIGHT = "PLAYWRIGHT"
    CRAWLEE_C = "CRAWLEE_C"
    CRAWLEE_D1 = "CRAWLEE_D1"
    CRAWLEE_D2 = "CRAWLEE_D2"


@dataclass(frozen=True)
class Task:
    """A benchmark task: which page, which fields, and the independently defined truth.

    `expected` is authored by hand and is never derived from any arm's output.
    """

    task_id: str
    path: str
    required_fields: tuple[str, ...]
    expected: dict[str, Any]
    notes: str = ""

    def __post_init__(self) -> None:
        missing = [f for f in self.required_fields if f not in self.expected]
        if missing:
            raise ValueError(
                f"task {self.task_id!r}: required fields absent from ground truth: {missing}"
            )


@dataclass(frozen=True)
class Document:
    """What an execution mode returns. Identical shape for every arm."""

    url: str
    status_code: int
    html: str
    execution_mode: ExecutionMode
    bytes_transferred: int | None = None


@dataclass(frozen=True)
class Candidate:
    """One value for one field, and the channel it was read from."""

    field: str
    value: Any
    source: EvidenceSource


@dataclass(frozen=True)
class Extraction:
    """Fields the extractor found. A field the extractor could not find is absent.

    Absence is meaningful — it is what separates `FAILED` from `FALSE_SUCCESS` —
    so extractors must omit fields rather than fill them with `None` or "".
    """

    record: dict[str, Any]
    # Every value the extractor saw, including the ones `record` discarded. Scoring
    # never reads this; it exists for the verification experiments.
    candidates: tuple[Candidate, ...] = ()


@dataclass(frozen=True)
class BenchmarkRecord:
    """One scored task result for one arm."""

    task_id: str
    arm: ExecutionMode
    result_state: ResultState
    # The adaptive arms run inside Crawlee's own scheduler, which does not expose a
    # per-request cost boundary. They record None rather than a fabricated number;
    # their cost is reported per run instead.
    wall_time_seconds: float | None
    cpu_time_seconds: float | None
    process_tree_rss_bytes: int | None
    browser_rendered: bool | None
    extracted_record: dict[str, Any] | None
    expected_record: dict[str, Any]
    error_type: str | None
    bytes_transferred: int | None
    # An adaptive result is meaningless without the predictor history that produced
    # it, so every record carries the regime and prior state it was measured under.
    regime: str | None = None
    predictor_state_context: str | None = None
    repetition: int = 0


@dataclass(frozen=True)
class RunMetadata:
    """Run-level information written alongside the raw JSONL results."""

    run_id: str
    python_version: str
    platform: str
    architecture: str
    dependencies: dict[str, str]
    playwright_version: str
    chromium_version: str
    browser_startup_seconds: float | None


def load_tasks(path: Path) -> tuple[Task, ...]:
    """Load ground truth from JSON. Ground truth is data, not code, on purpose."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    return tuple(
        Task(
            task_id=entry["task_id"],
            path=entry["path"],
            required_fields=tuple(entry["required_fields"]),
            expected=entry["expected"],
            notes=entry.get("notes", ""),
        )
        for entry in raw
    )
