"""Ten-target selection, exactly as declared in PROBE-PROTOCOL.md §6.

Selection never inspects structured data, endpoints, rendering behaviour, disagreement,
or extraction success. It reads a rank list, a homepage's links, and robots.txt.
"""

from __future__ import annotations

import json
import random
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx
from selectolax.parser import HTMLParser

from realworld.frame import PRODUCT_PATH
from scavenge import robots
from scavenge.acquire import USER_AGENT

SEED = 20260818
FRAME_DEPTH = 10_000
TARGET_COUNT = 10
PACING_SECONDS = 2.0
MIN_PATH_SEGMENTS = 2
HTTP_OK = 200


@dataclass(frozen=True)
class Draw:
    rank: int
    domain: str
    disposition: str
    target: str | None = None


def _homepage(client: httpx.Client, domain: str) -> httpx.Response | None:
    try:
        return client.get(f"https://{domain}/")
    except httpx.HTTPError:
        return None


def _first_deep_link(html: str, base: str, host: str, *, product_only: bool) -> str | None:
    """First same-host link matching the declared shape, in document order.

    `product_only` applies Addendum B's sub-frame: the path pattern frozen in
    PILOT-PROTOCOL.md A1. It reads the URL path and nothing else — never markup, never a
    price, never a network request.
    """
    for node in HTMLParser(html).css("a[href]"):
        candidate = urljoin(base, node.attributes.get("href") or "")
        parts = urlparse(candidate)
        if parts.scheme not in {"http", "https"} or parts.netloc != host:
            continue
        if product_only:
            if PRODUCT_PATH.search(parts.path):
                return f"{parts.scheme}://{parts.netloc}{parts.path}"
            continue
        if len([s for s in parts.path.split("/") if s]) >= MIN_PATH_SEGMENTS:
            return f"{parts.scheme}://{parts.netloc}{parts.path}"
    return None


def _progress(drawn: int, domain: str, disposition: str, accepted: int) -> None:
    """Flushed so a stalled run can be diagnosed from its output rather than by replaying
    the draw. Observability only: nothing here influences selection."""
    print(
        f"draw {drawn} | {domain} | {disposition} | qualified {accepted}/{TARGET_COUNT}",
        file=sys.stderr,
        flush=True,
    )


def select(frame_csv: Path, *, product_only: bool = False) -> list[Draw]:
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
    with httpx.Client(
        follow_redirects=True, timeout=20.0, headers={"User-Agent": USER_AGENT}
    ) as client:
        for rank, domain in order:
            if accepted >= TARGET_COUNT:
                break
            time.sleep(PACING_SECONDS)
            drawn += 1
            home_robots = robots.fetch(f"https://{domain}/", USER_AGENT)
            if not home_robots.allowed:
                draws.append(Draw(rank, domain, home_robots.disposition.value))
                _progress(drawn, domain, home_robots.disposition.value, accepted)
                continue
            response = _homepage(client, domain)
            if response is None:
                draws.append(Draw(rank, domain, "UNREACHABLE"))
                _progress(drawn, domain, "UNREACHABLE", accepted)
                continue
            if response.status_code != HTTP_OK:
                draws.append(Draw(rank, domain, f"HTTP_{response.status_code}"))
                _progress(drawn, domain, f"HTTP_{response.status_code}", accepted)
                continue
            host = urlparse(str(response.url)).netloc
            target = _first_deep_link(
                response.text, str(response.url), host, product_only=product_only
            )
            if target is None:
                missing = "NO_PRODUCT_LINK" if product_only else "NO_DEEP_LINK"
                draws.append(Draw(rank, domain, missing))
                _progress(drawn, domain, missing, accepted)
                continue
            target_robots = robots.fetch(target, USER_AGENT)
            if not target_robots.allowed:
                draws.append(Draw(rank, domain, f"TARGET_{target_robots.disposition.value}"))
                _progress(drawn, domain, f"TARGET_{target_robots.disposition.value}", accepted)
                continue
            draws.append(Draw(rank, domain, "SELECTED", target))
            accepted += 1
            _progress(drawn, domain, "SELECTED", accepted)
    return draws


if __name__ == "__main__":
    result = select(Path(sys.argv[1]), product_only="--product" in sys.argv)
    Path(sys.argv[2]).write_text(json.dumps([asdict(d) for d in result], indent=2))
    for draw in result:
        print(draw.disposition, draw.rank, draw.domain, draw.target or "")
