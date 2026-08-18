"""Helpers shared by the field adapters: HTML-embedded JSON, and walking JSON for keys.

Not an abstraction layer — two field modules needed the same two functions, so they live
in one place instead of two.
"""

from __future__ import annotations

import html as html_entities
import json
import re
from collections.abc import Iterator

from selectolax.parser import HTMLParser

from scavenge.models import PAGE_SUBJECT, Subject, SubjectScope

MAX_JSON_DEPTH = 8
MAX_MATCHES = 20


def decode(raw: object) -> str:
    """Entity-decode before any parsing.

    JSON embedded in HTML routinely carries entity-escaped symbols. Left encoded,
    `&#8377;4400` parses as the amount 8377 — the entity's own digits — which garbled a
    whole report in the first ten-target run.
    """
    return html_entities.unescape(str(raw))


def embedded_payloads(html: str) -> Iterator[tuple[str, object]]:
    """`<script>` JSON that is not schema.org — hydration and application state.

    schema.org blocks are excluded because they are the structured-data channel; folding
    them in would report one observation twice as if it were two.
    """
    for index, node in enumerate(HTMLParser(html).css("script")):
        if (node.attributes.get("type") or "").lower() == "application/ld+json":
            continue
        text = node.text().strip()
        if not text.startswith(("{", "[")):
            continue
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            continue
        yield node.attributes.get("id") or f"script[{index}]", payload


def find_keys(
    node: object,
    pattern: re.Pattern[str],
    pointer: str = "",
    depth: int = 0,
    out: list[tuple[str, object, dict[str, str]]] | None = None,
) -> list[tuple[str, object, dict[str, str]]]:
    """Every matching key with a scalar value, its JSON pointer, and its sibling scalars.

    Siblings travel with the match because a price needs its neighbouring currency and an
    availability value sometimes needs its neighbouring label.
    """
    if out is None:
        out = []
    if depth > MAX_JSON_DEPTH or len(out) >= MAX_MATCHES:
        return out
    if isinstance(node, dict):
        siblings = {k: str(v) for k, v in node.items() if isinstance(v, str | int | float)}
        for key, value in node.items():
            if pattern.search(key) and isinstance(value, str | int | float):
                out.append((f"{pointer}/{key}", value, siblings))
            else:
                find_keys(value, pattern, f"{pointer}/{key}", depth + 1, out)
    elif isinstance(node, list):
        for index, item in enumerate(node):
            find_keys(item, pattern, f"{pointer}/{index}", depth + 1, out)
    return out


_ARRAY_INDEX = re.compile(r"^(.*)/(\d+)(/.*)?$")
# Two entries side by side are enough to establish that an array holds sibling entities.
_MIN_PEERS = 2


def sibling_subject(pointer: str, matches: list[tuple[str, object, dict[str, str]]]) -> Subject:
    """Are there several of these, side by side in one array? Then they are separate entities.

    This is the whole of the JSON subject rule. Search hits at `/results/0/hits/{0..3}/…` and
    store rows at `/stores/{0..n}/…` are siblings describing different products or places;
    correlating them against the page's own value produced spurious disagreements in release
    validation. A single occurrence stays page-scoped, so ordinary payloads remain useful.
    """
    match = _ARRAY_INDEX.match(pointer)
    if match is None:
        return PAGE_SUBJECT
    prefix, index, suffix = match.group(1), match.group(2), match.group(3) or ""
    peers = set()
    for other, _, _ in matches:
        peer = _ARRAY_INDEX.match(other)
        if peer and peer.group(1) == prefix and (peer.group(3) or "") == suffix:
            peers.add(peer.group(2))
    if len(peers) < _MIN_PEERS:
        return PAGE_SUBJECT
    return Subject(
        SubjectScope.SIBLING,
        f"{prefix}/{index}",
        f"one of {len(peers)} sibling entries under {prefix}",
    )
