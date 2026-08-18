"""Human-readable rendering of an EvidenceReport.

Evidence first. There is deliberately no "suggested strategy" line: the retest measured
the evidence to be stronger than the recommendation layer built on top of it, so the
recommendation was removed rather than demoted.
"""

from __future__ import annotations

from scavenge.models import Channel, EvidenceReport, Observation


def render(report: EvidenceReport) -> str:
    lines: list[str] = [f"TARGET\n  {report.target}", "", f"FIELD: {report.field}"]

    for channel in Channel:
        found = [o for o in report.observations if o.channel is channel]
        if not found:
            lines.append(f"  {channel.value:<16} not observed")
            continue
        lines.extend(_observation_lines(channel, found))

    acquisition = report.acquisition
    lines += [
        "",
        "ACQUISITION",
        f"  HTTP    {acquisition.http_status}  {acquisition.http_bytes} bytes"
        f"  {acquisition.http_seconds}s",
        f"  RENDER  {acquisition.render_status.value}"
        + (f"  {acquisition.render_detail}" if acquisition.render_detail else ""),
        f"  JSON responses observed: {acquisition.json_responses}"
        + ("  (capped)" if acquisition.responses_truncated else ""),
    ]
    if report.warnings:
        lines += ["", "WARNINGS"] + [f"  • {w}" for w in report.warnings]
    return "\n".join(lines) + "\n"


def _observation_lines(channel: Channel, found: list[Observation]) -> list[str]:
    lines = []
    for observation in found:
        value = str(observation.normalized_value) if observation.normalized_value else "—"
        lines.append(f"  {channel.value:<16} {value}   [{observation.id}]")
        lines.append(f"  {'':<16}   raw:    {observation.raw!r}")
        lines.append(f"  {'':<16}   source: {_source(observation)}")
        if observation.note:
            lines.append(f"  {'':<16}   note:   {observation.note}")
    return lines


def _source(observation: Observation) -> str:
    provenance = observation.provenance
    parts = [
        provenance.request,
        provenance.script,
        provenance.selector,
        provenance.pointer,
        provenance.content_type,
    ]
    return " ".join(p for p in parts if p) or "(none recorded)"


__all__ = ["render"]
