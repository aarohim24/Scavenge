"""Arm E: reject a cheap extraction when the cheap document contradicts itself.

E does not ask whether a value is globally true, which one document usually cannot
answer. It asks the narrower question: does this document contain evidence that
contradicts the value we are about to trust? Absence of contradiction is not proof
of correctness, and E does not treat it as such.

Single document only. No history, no browser output, no ground truth, no learning.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from crawlbench.models import Candidate

_DIGITS = re.compile(r"\d[\d,]*")


class Decision(StrEnum):
    ACCEPT = "ACCEPT"
    REJECT_CONFLICT = "REJECT_CONFLICT"
    REJECT_INCOMPLETE = "REJECT_INCOMPLETE"


def normalize(field: str, value: Any) -> Any:
    """Just enough normalisation that agreeing sources are not read as disagreeing.

    `1999`, `"1999"` and `"1,999"` are one value; `"INR"` and `"inr"` are one value.
    Nothing here is fuzzy or semantic — two values are equal or they are not.
    """
    if field == "price":
        if isinstance(value, bool):
            return value
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            match = _DIGITS.search(value)
            return int(match.group().replace(",", "")) if match else value
        return value
    if isinstance(value, str):
        return value.strip().upper() if field == "currency" else value.strip()
    return value


def conflicting_sources(field: str, candidates: Sequence[Candidate]) -> tuple[tuple[str, Any], ...]:
    """Distinct normalised values for `field` that came from different channels.

    Two candidates only count as disagreeing when their sources differ. Two DOM
    selectors returning different text are one channel disagreeing with itself,
    which is a weaker signal than two independent channels disagreeing, so v0.4
    does not act on it.
    """
    by_source: dict[str, Any] = {}
    for candidate in candidates:
        if candidate.field != field:
            continue
        by_source.setdefault(candidate.source, normalize(field, candidate.value))

    values = set(by_source.values())
    if len(values) <= 1:
        return ()
    return tuple(sorted(by_source.items()))


def verify(
    record: Mapping[str, Any],
    candidates: Sequence[Candidate],
    fields: Sequence[str],
) -> Decision:
    """Accept unless a required field is missing or independently contradicted."""
    if any(record.get(field) in (None, "") for field in fields):
        return Decision.REJECT_INCOMPLETE

    if any(conflicting_sources(field, candidates) for field in fields):
        return Decision.REJECT_CONFLICT

    return Decision.ACCEPT


@dataclass(frozen=True)
class Trace:
    """Why E decided what it decided, for manual review of individual fixtures."""

    decision: Decision
    conflicts: dict[str, tuple[tuple[str, Any], ...]]

    @classmethod
    def of(
        cls,
        record: Mapping[str, Any],
        candidates: Sequence[Candidate],
        fields: Sequence[str],
    ) -> Trace:
        return cls(
            decision=verify(record, candidates, fields),
            conflicts={
                field: conflict
                for field in fields
                if (conflict := conflicting_sources(field, candidates))
            },
        )
