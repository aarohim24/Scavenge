"""The evidence model: what was observed, where it came from, and how observations relate.

Deliberately small. One `EvidenceReport` per engine call. Nothing here knows what a price
or an availability state means — a field type supplies structured normalized values, and
correlation compares them through one private key function. That is what lets a second
field cost one module rather than a second engine.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal
from enum import StrEnum
from typing import Any

SCHEMA_VERSION = 3
# Cross-channel relations are pairwise, so the observation count bounds the report size.
# Beyond this the extra candidates are dropped and a warning says so — never silently.
MAX_VALUED_OBSERVATIONS = 12


class Channel(StrEnum):
    RAW_DOM = "RAW_DOM"
    STRUCTURED_DATA = "STRUCTURED_DATA"
    EMBEDDED_STATE = "EMBEDDED_STATE"
    RENDERED_DOM = "RENDERED_DOM"
    NETWORK_JSON = "NETWORK_JSON"


class ObservationStatus(StrEnum):
    OK = "OK"
    PARSE_FAILURE = "PARSE_FAILURE"


class RenderStatus(StrEnum):
    """Rendering outcomes are evidence, not exceptions."""

    OK = "OK"
    PARTIAL_RENDER = "PARTIAL_RENDER"
    RENDERING_TIMEOUT = "RENDERING_TIMEOUT"
    RENDERING_FAILED = "RENDERING_FAILED"
    BLOCKED_OR_CHALLENGED = "BLOCKED_OR_CHALLENGED"
    NOT_ATTEMPTED = "NOT_ATTEMPTED"


class AvailabilityState(StrEnum):
    """Only states we can read unambiguously. Anything else stays raw with no normalized
    value, rather than being promoted to a semantic 'unknown' we did not observe."""

    IN_STOCK = "IN_STOCK"
    OUT_OF_STOCK = "OUT_OF_STOCK"


@dataclass(frozen=True)
class MoneyValue:
    amount: Decimal
    currency: str | None

    def __str__(self) -> str:
        return f"{self.amount} {self.currency or '?'}"


@dataclass(frozen=True)
class AvailabilityValue:
    state: AvailabilityState

    def __str__(self) -> str:
        return self.state.value


NormalizedValue = MoneyValue | AvailabilityValue


def comparison_key(value: NormalizedValue) -> tuple[str | Decimal, ...]:
    """Private to correlation: the hashable form two observations are compared through.

    The amount stays a `Decimal` rather than becoming a string, because `0.00` and `0.0`
    are the same amount written two ways — a real page reported them as DIFFERENT until
    this was fixed. Currency is part of the key, and its absence is explicit, so an
    unknown currency never silently matches a known one.
    """
    if isinstance(value, MoneyValue):
        return ("money", value.amount, value.currency or "")
    return ("availability", value.state.value)


def comparable(left: NormalizedValue, right: NormalizedValue) -> bool:
    """Different currencies describe different quantities; comparing them is meaningless.

    An amount whose currency is unknown is *not* comparable to one whose currency is known:
    reporting `499 ?` EQUAL to `499 USD` would assert a match we cannot support.
    """
    if isinstance(left, MoneyValue) and isinstance(right, MoneyValue):
        if left.currency is None or right.currency is None:
            return left.currency == right.currency
        return left.currency == right.currency
    return type(left) is type(right)


@dataclass(frozen=True)
class Provenance:
    """Why this observation exists. Populated per channel; unused parts stay None."""

    selector: str | None = None
    pointer: str | None = None
    script: str | None = None
    request: str | None = None
    content_type: str | None = None


class SubjectScope(StrEnum):
    """Which entity an observation describes.

    Deliberately three states and no resolver. `SIBLING` means the observation sits beside
    others of its kind — a search hit, a store-locator row, a financing line — so it
    describes *an* entity but not necessarily the page's. `UNKNOWN` means we have no
    deterministic evidence either way.
    """

    PAGE = "PAGE"
    SIBLING = "SIBLING"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class Subject:
    scope: SubjectScope = SubjectScope.PAGE
    key: str = ""  # distinguishes siblings from one another; empty for PAGE/UNKNOWN
    reason: str = ""  # why this scope was assigned, so a suppressed relation is explainable


PAGE_SUBJECT = Subject()


class SubjectMatch(StrEnum):
    SAME = "SAME_SUBJECT"
    DIFFERENT = "DIFFERENT_SUBJECT"
    UNKNOWN = "SUBJECT_UNKNOWN"


def subject_match(left: Subject, right: Subject) -> SubjectMatch:
    """Comparable only on deterministic sameness. Anything else refuses to compare.

    False certainty is worse than a missing relation: a spurious DIFFERENT between a
    product price and a financing-table amount is an outright wrong answer, while a
    missing relation is merely silence.
    """
    if SubjectScope.UNKNOWN in (left.scope, right.scope):
        return SubjectMatch.UNKNOWN
    if left.scope is SubjectScope.PAGE and right.scope is SubjectScope.PAGE:
        return SubjectMatch.SAME
    if left.scope is right.scope and left.key == right.key:
        return SubjectMatch.SAME
    return SubjectMatch.DIFFERENT


@dataclass(frozen=True)
class Candidate:
    """What a field adapter yields before the engine assigns it an id and a channel."""

    value: NormalizedValue | None
    raw: str
    provenance: Provenance
    note: str = ""
    subject: Subject = PAGE_SUBJECT


@dataclass(frozen=True)
class Observation:
    id: str  # noqa: A003 - "id" is the field name in the public JSON schema
    channel: Channel
    normalized_value: NormalizedValue | None
    raw: str
    provenance: Provenance
    status: ObservationStatus = ObservationStatus.OK
    note: str = ""
    subject: Subject = PAGE_SUBJECT


@dataclass(frozen=True)
class Acquisition:
    http_status: int | None
    http_bytes: int
    http_seconds: float
    # Real-world validation found a raw body reading "Are you a human?" being treated as an
    # ordinary empty page. The model could not express "the cheap fetch was blocked", so
    # this records the signal that says so. Empty means no challenge was detected.
    http_challenge: str
    render_status: RenderStatus
    render_detail: str
    render_seconds: float
    json_responses: int
    responses_truncated: bool


@dataclass(frozen=True)
class EvidenceReport:
    """Observations and how they were acquired — deliberately **no** relations.

    v0.1 published cross-observation relations and real-world validation showed every
    `DIFFERENT` it produced on live storefronts was wrong: the two observations described
    different entities (a second Product block, a mini-cart message, an upsell tile, a cart
    total). Establishing subject identity needs entity resolution, which this engine will
    not do. So comparison is left to the reader, who can see the provenance and decide.
    See OSS-FINAL-CORRECTNESS.md.
    """

    target: str
    field: str
    observations: tuple[Observation, ...]
    acquisition: Acquisition
    warnings: tuple[str, ...] = ()
    schema_version: int = SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        """Stable JSON shape. Decimals become strings so no precision is lost in transit."""
        return {
            "schema_version": self.schema_version,
            "target": self.target,
            "field": self.field,
            "observations": [_observation_dict(o) for o in self.observations],
            "acquisition": asdict(self.acquisition),
            "warnings": list(self.warnings),
        }


def _observation_dict(observation: Observation) -> dict[str, Any]:
    value = observation.normalized_value
    if isinstance(value, MoneyValue):
        normalized: dict[str, Any] | None = {
            "kind": "money",
            "amount": str(value.amount),
            "currency": value.currency,
        }
    elif isinstance(value, AvailabilityValue):
        normalized = {"kind": "availability", "state": value.state.value}
    else:
        normalized = None
    return {
        "id": observation.id,
        "channel": observation.channel.value,
        "normalized_value": normalized,
        "raw": observation.raw,
        "provenance": {k: v for k, v in asdict(observation.provenance).items() if v is not None},
        "subject": {
            "scope": observation.subject.scope.value,
            "key": observation.subject.key,
            "reason": observation.subject.reason,
        },
        "status": observation.status.value,
        "note": observation.note,
    }
