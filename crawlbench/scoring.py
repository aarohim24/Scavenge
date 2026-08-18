"""Deterministic scoring of an extraction against independently defined ground truth.

Scoring takes exactly two inputs: what the extractor produced, and what the task
declares to be true. No arm's output is ever consulted as an oracle, which is why
this module cannot see `Document` or `ExecutionMode` at all.
"""

from __future__ import annotations

from crawlbench.models import Extraction, ResultState, Task


def score(extraction: Extraction, task: Task) -> ResultState:
    """Classify one extraction as CORRECT, FALSE_SUCCESS, or FAILED."""
    if missing_required_fields(extraction, task):
        return ResultState.FAILED

    if all(extraction.record[field] == task.expected[field] for field in task.required_fields):
        return ResultState.CORRECT

    # Every required field was produced, so the extractor claimed a complete
    # result. It was wrong. That is the outcome this benchmark exists to count.
    return ResultState.FALSE_SUCCESS


def missing_required_fields(extraction: Extraction, task: Task) -> tuple[str, ...]:
    """Required fields the extractor did not produce.

    A field present with value `None` counts as missing: the extractor did not
    claim a value for it.
    """
    return tuple(
        field
        for field in task.required_fields
        if field not in extraction.record or extraction.record[field] is None
    )
