"""Candidate-domain reconnaissance and eligibility, per PILOT-PROTOCOL.md Addendum A2."""

from __future__ import annotations

import json
import random
from dataclasses import asdict, dataclass
from pathlib import Path

from realworld.collect import PoliteFetcher, robots_for
from realworld.extract import dom_prices, jsonld_prices, page_language
from realworld.frame import MIN_PRODUCT_URLS, PROBE_PASS, PROBE_SIZE, discover

SEED = 20260817

# ~40 candidates spanning retailers, platforms, categories and regions. Chosen for
# breadth before any markup was inspected, and NOT for weak bot protection.
CANDIDATES = (
    "www.target.com",
    "www.walmart.com",
    "www.bestbuy.com",
    "www.homedepot.com",
    "www.lowes.com",
    "www.macys.com",
    "www.nordstrom.com",
    "www.wayfair.com",
    "www.newegg.com",
    "www.bhphotovideo.com",
    "www.allbirds.com",
    "www.rothys.com",
    "www.brooklinen.com",
    "www.drsquatch.com",
    "www.warbyparker.com",
    "casper.com",
    "www.glossier.com",
    "us.gymshark.com",
    "www.johnlewis.com",
    "www.argos.co.uk",
    "www.waterstones.com",
    "www.screwfix.com",
    "www.currys.co.uk",
    "www.boots.com",
    "www.next.co.uk",
    "www.asos.com",
    "www.ikea.com",
    "www.zalando.co.uk",
    "www.decathlon.com",
    "www.thomann.de",
    "www.conrad.de",
    "www.mediamarkt.de",
    "www.fnac.com",
    "www.bol.com",
    "www.coolblue.nl",
    "www.lush.com",
    "www.uniqlo.com",
    "www.muji.com",
    "www.sweetwater.com",
    "www.kogan.com",
)


@dataclass(frozen=True)
class DomainReport:
    domain: str
    disposition: str
    product_urls: int
    discovery: str
    probe_fetched: int
    probe_two_channels: int
    note: str


def assess(domain: str, fetcher: PoliteFetcher, rng: random.Random) -> DomainReport:
    robots = robots_for(domain, fetcher)
    if robots is None:
        return DomainReport(domain, "COLLECTION_BLOCKED", 0, "-", 0, 0, "robots unreachable")

    urls, method = discover(domain, robots, fetcher)
    if not urls:
        return DomainReport(domain, "NO_PRODUCT_DISCOVERY", 0, method, 0, 0, "no product URLs")
    if len(urls) < MIN_PRODUCT_URLS:
        return DomainReport(
            domain,
            "INSUFFICIENT_PRODUCT_URLS",
            len(urls),
            method,
            0,
            0,
            f"{len(urls)} < {MIN_PRODUCT_URLS}",
        )

    probe = list(urls)
    rng.shuffle(probe)
    fetched = two_channels = 0
    for url in probe[:PROBE_SIZE]:
        outcome = fetcher.get(url)
        if not outcome.ok or outcome.body is None:
            continue
        fetched += 1
        html = outcome.body
        dom, jsonld = dom_prices(html, page_language(html)), jsonld_prices(html)
        if dom.chosen and jsonld.chosen and dom.chosen.money and jsonld.chosen.money:
            left, right = dom.chosen.money, jsonld.chosen.money
            if not (left.currency and right.currency and left.currency != right.currency):
                two_channels += 1

    if two_channels >= PROBE_PASS:
        return DomainReport(domain, "ELIGIBLE", len(urls), method, fetched, two_channels, "")
    disposition = "COLLECTION_BLOCKED" if fetched == 0 else "INSUFFICIENT_CHANNEL_COVERAGE"
    return DomainReport(
        domain,
        disposition,
        len(urls),
        method,
        fetched,
        two_channels,
        f"{two_channels}/{PROBE_SIZE} probe pages comparable",
    )


def run(path: Path) -> list[DomainReport]:
    fetcher = PoliteFetcher()
    rng = random.Random(SEED)
    reports = []
    for domain in CANDIDATES:
        report = assess(domain, fetcher, rng)
        reports.append(report)
        print(
            f"  {report.domain:24}{report.disposition:30}"
            f"{report.product_urls:>6} {report.discovery}"
        )
    path.write_text(json.dumps([asdict(r) for r in reports], indent=2) + "\n")
    return reports
