"""Retest target selection, exactly as declared in PROBE-RETEST-PROTOCOL.md §2.

Selection reads a rank list, a homepage's link paths, and whether any price exists on the
rendered page. It never inspects channels, endpoints, disagreement, or what `probe` would
conclude.
"""

from __future__ import annotations

import json
import random
import re
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx
from selectolax.parser import HTMLParser

from realworld.frame import PRODUCT_PATH
from scavenge import robots
from scavenge.acquire import USER_AGENT, Renderer, rendering_session

SEED = 20260819
FRAME_DEPTH = 10_000
TARGET_COUNT = 10
PACING_SECONDS = 2.0
MIN_PRODUCT_LINKS = 5
HTTP_OK = 200
# A price concept: a currency symbol adjacent to digits, checked on the rendered page.
CURRENCY_AMOUNT = re.compile(r"(?:\$|£|€|₹|¥|zł)\s?\d")


@dataclass(frozen=True)
class Draw:
    rank: int
    domain: str
    disposition: str
    target: str | None = None


def product_detail_paths(html: str, base: str, host: str) -> list[str]:
    """Links matching the product pattern *and* carrying a further segment after it.

    The trailing segment is what separates a product page from a `/products/` index — the
    confusion that spoiled the previous frame.
    """
    found: dict[str, None] = {}
    for node in HTMLParser(html).css("a[href]"):
        candidate = urljoin(base, node.attributes.get("href") or "")
        parts = urlparse(candidate)
        if parts.scheme not in {"http", "https"} or parts.netloc != host:
            continue
        match = PRODUCT_PATH.search(parts.path)
        if match is None:
            continue
        if not parts.path[match.end() :].strip("/"):
            continue
        found.setdefault(f"{parts.scheme}://{parts.netloc}{parts.path}")
    return list(found)


def select(frame_csv: Path) -> list[Draw]:
    ranked: list[tuple[int, str]] = []
    for line in frame_csv.read_text().splitlines():
        rank_text, _, domain = line.partition(",")
        if int(rank_text) > FRAME_DEPTH:
            break
        ranked.append((int(rank_text), domain))
    order = list(ranked)
    random.Random(SEED).shuffle(order)

    draws: list[Draw] = []
    accepted = 0
    drawn = 0
    with (
        httpx.Client(
            follow_redirects=True, timeout=20.0, headers={"User-Agent": USER_AGENT}
        ) as client,
        rendering_session() as renderer,
    ):
        for rank, domain in order:
            if accepted >= TARGET_COUNT:
                break
            time.sleep(PACING_SECONDS)
            drawn += 1
            disposition, target = _evaluate(client, renderer, domain)
            draws.append(Draw(rank, domain, disposition, target))
            if disposition == "SELECTED":
                accepted += 1
            _progress(drawn, domain, disposition, accepted)
    return draws


def _evaluate(  # noqa: PLR0911 - each return is a distinct, recorded disposition
    client: httpx.Client, renderer: Renderer, domain: str
) -> tuple[str, str | None]:
    home = f"https://{domain}/"
    home_robots = robots.fetch(home, USER_AGENT)
    if not home_robots.allowed:
        return home_robots.disposition.value, None
    try:
        response = client.get(home)
    except httpx.HTTPError:
        return "UNREACHABLE", None
    if response.status_code != HTTP_OK:
        return f"HTTP_{response.status_code}", None

    host = urlparse(str(response.url)).netloc
    links = product_detail_paths(response.text, str(response.url), host)
    if len(links) < MIN_PRODUCT_LINKS:
        return "NOT_A_STOREFRONT", None

    target = links[0]
    if not robots.fetch(target, USER_AGENT).allowed:
        return "TARGET_ROBOTS_DISALLOWED", None

    observation = renderer.render(target)
    if not observation.html:
        return "TARGET_UNRENDERABLE", None
    if not CURRENCY_AMOUNT.search(HTMLParser(observation.html).text()):
        return "NO_PRICE_CONCEPT", None
    return "SELECTED", target


def _progress(drawn: int, domain: str, disposition: str, accepted: int) -> None:
    print(
        f"draw {drawn} | {domain} | {disposition} | qualified {accepted}/{TARGET_COUNT}",
        file=sys.stderr,
        flush=True,
    )


if __name__ == "__main__":
    result = select(Path(sys.argv[1]))
    Path(sys.argv[2]).write_text(json.dumps([asdict(d) for d in result], indent=2))
