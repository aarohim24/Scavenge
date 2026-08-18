"""The engine: one call, one evidence report.

    inspect_field(url, field) -> EvidenceReport

It acquires, observes and correlates. It does not decide which value is correct, which
price the caller meant, or whether a browser is "needed" — those are judgements for a
human or an agent, and keeping them out is the product boundary.
"""

from __future__ import annotations

from types import ModuleType

from scavenge import availability, price
from scavenge.acquire import Renderer, fetch_raw
from scavenge.challenge import detect as detect_challenge
from scavenge.context import build as build_context
from scavenge.models import (
    MAX_VALUED_OBSERVATIONS,
    Acquisition,
    Candidate,
    Channel,
    EvidenceReport,
    Observation,
    ObservationStatus,
    RenderStatus,
)

FIELDS: dict[str, ModuleType] = {"price": price, "availability": availability}


class UnknownFieldError(ValueError):
    """Raised rather than returning an empty report: an unsupported field is not 'no evidence'."""


def inspect_field(
    url: str, field: str, *, renderer: Renderer | None = None, allow_private: bool = False
) -> EvidenceReport:
    if field not in FIELDS:
        raise UnknownFieldError(f"unsupported field {field!r}; supported: {sorted(FIELDS)}")
    adapter = FIELDS[field]

    raw = fetch_raw(url, allow_private=allow_private)
    collected: list[tuple[Channel, Candidate]] = []
    # A challenge page is not the target in any channel: reading a value out of an
    # interstitial would be a fabricated observation.
    http_challenge = detect_challenge(raw.body) or ""
    context = build_context(raw.url, raw.body)
    if not http_challenge:
        for channel, candidates in (
            (Channel.RAW_DOM, adapter.from_dom(raw.body, context)),
            (Channel.STRUCTURED_DATA, adapter.from_structured(raw.body, context)),
            (Channel.EMBEDDED_STATE, adapter.from_embedded(raw.body, context)),
        ):
            collected += [(channel, c) for c in candidates]

    rendered = renderer.render(url) if renderer is not None else None
    blocked = rendered is not None and rendered.status is RenderStatus.BLOCKED_OR_CHALLENGED
    # A challenge page is not the target. Reading a "price" out of an interstitial would be
    # a fabricated observation, so the rendered channels are skipped and the report says so.
    if rendered is not None and rendered.html and not blocked:
        collected += [(Channel.RENDERED_DOM, c) for c in adapter.from_dom(rendered.html, context)]
        collected += [
            (Channel.NETWORK_JSON, c) for c in adapter.from_network(rendered.responses, context)
        ]

    observations, warnings = _observations(collected)
    if http_challenge:
        warnings += (
            f"raw HTTP response looks like a block or challenge — {http_challenge}; "
            "raw, structured and embedded channels were not read",
        )
    if blocked and rendered is not None:
        warnings += (
            f"rendered page looks like a block or challenge — {rendered.detail}; "
            "rendered and network channels were not read",
        )
    return EvidenceReport(
        target=raw.url,
        field=field,
        observations=observations,
        acquisition=Acquisition(
            http_status=raw.status,
            http_bytes=len(raw.body),
            http_seconds=round(raw.seconds, 3),
            http_challenge=http_challenge,
            render_status=rendered.status if rendered else RenderStatus.NOT_ATTEMPTED,
            render_detail=rendered.detail if rendered else "",
            render_seconds=round(rendered.seconds, 3) if rendered else 0.0,
            json_responses=len(rendered.responses) if rendered else 0,
            responses_truncated=bool(rendered and rendered.overflowed),
        ),
        warnings=warnings,
    )


def _observations(
    collected: list[tuple[Channel, Candidate]],
) -> tuple[tuple[Observation, ...], tuple[str, ...]]:
    """Ids are `channel:index` in collection order, so a report is stable across runs."""
    out: list[Observation] = []
    warnings: list[str] = []
    counts: dict[Channel, int] = {}
    valued = 0
    for channel, candidate in collected:
        if candidate.value is not None and valued >= MAX_VALUED_OBSERVATIONS:
            warnings.append(
                f"more than {MAX_VALUED_OBSERVATIONS} values were found; "
                "later candidates were dropped from this report"
            )
            break
        index = counts.get(channel, 0)
        counts[channel] = index + 1
        if candidate.value is not None:
            valued += 1
        out.append(
            Observation(
                id=f"{channel.value.lower()}:{index}",
                channel=channel,
                normalized_value=candidate.value,
                raw=candidate.raw,
                provenance=candidate.provenance,
                status=(
                    ObservationStatus.OK
                    if candidate.value is not None
                    else ObservationStatus.PARSE_FAILURE
                ),
                note=candidate.note,
                subject=candidate.subject,
            )
        )
    return tuple(out), tuple(dict.fromkeys(warnings))
