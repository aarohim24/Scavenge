"""Arm E real-world pilot: does channel disagreement predict correctable cheap errors?

Methodology is frozen in PILOT-PROTOCOL.md. This module only collects and counts; it
does not modify Arm E, and it makes no decision that the protocol did not predeclare.
"""

from __future__ import annotations

import json
import random
import re
import time
import urllib.robotparser
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

import httpx
from playwright.sync_api import sync_playwright
from selectolax.parser import HTMLParser

USER_AGENT = "CrawlBenchResearch/0.1 (methodology pilot; low rate; honours robots.txt)"
SEED = 20260817
MAX_USABLE_PER_DOMAIN = 15
MAX_ATTEMPTS_PER_DOMAIN = 40
REQUEST_SPACING_SECONDS = 1.0
HTTP_OK = 200
MAX_JSONLD_DEPTH = 6
MAX_SITEMAP_URLS = 5000
MIN_COMPARABLE_CHANNELS = 2

# Fixed by hand for breadth of retail category and geography, before any page markup
# was inspected. Domains that block us are recorded as failures, not replaced.
DOMAINS = (
    "www.ikea.com",
    "www.wayfair.com",
    "www.target.com",
    "www.walmart.com",
    "www.zalando.co.uk",
    "www.johnlewis.com",
    "www.decathlon.com",
    "www.thomann.de",
    "www.sweetwater.com",
    "books.toscrape.com",
)

# A currency amount: optional symbol, digits, optional grouping and decimals.
_AMOUNT = re.compile(
    r"(?:[$£€₹¥]|USD|EUR|GBP|INR)?\s*(\d{1,3}(?:[,\s]\d{3})*(?:\.\d{2})?|\d+(?:\.\d{2})?)"
)
_PRICE_ATTR = re.compile(r"price", re.IGNORECASE)


def normalize_price(raw: object) -> int | None:
    """Protocol section 4. Digits only, grouping removed, compared as an integer."""
    if isinstance(raw, bool):
        return None
    if isinstance(raw, int | float):
        return int(round(float(raw)))
    if not isinstance(raw, str):
        return None
    match = _AMOUNT.search(raw)
    if match is None:
        return None
    try:
        return int(round(float(match.group(1).replace(",", "").replace(" ", ""))))
    except ValueError:
        return None


def dom_price(html: str) -> int | None:
    """Declared DOM rule: the first innermost element whose class/id/data-testid
    mentions 'price' and whose own text parses as a currency amount, in document order.
    """
    tree = HTMLParser(html)
    for node in tree.css("*"):
        attrs = node.attributes
        marker = " ".join(
            str(attrs.get(key) or "") for key in ("class", "id", "data-testid", "itemprop")
        )
        if not _PRICE_ATTR.search(marker):
            continue
        if any(
            _PRICE_ATTR.search(
                " ".join(
                    str(c.attributes.get(k) or "")
                    for k in ("class", "id", "data-testid", "itemprop")
                )
            )
            for c in node.css("*")
        ):
            continue  # prefer the innermost price-ish element
        price = normalize_price(node.text(deep=True, strip=True))
        if price:
            return price
    return None


def jsonld_price(html: str) -> int | None:
    """Price from a schema.org Product/Offer block."""
    tree = HTMLParser(html)
    for node in tree.css('script[type="application/ld+json"]'):
        raw = node.text().strip()
        if not raw:
            continue
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            continue
        price = _find_offer_price(parsed)
        if price is not None:
            return price
    return None


def _find_offer_price(node: object, depth: int = 0) -> int | None:
    """First `price` found under an offers/Product structure. Multiple differing
    offer prices are surfaced by returning the first; the auditor marks such pages
    AMBIGUOUS per protocol section 3."""
    if depth > MAX_JSONLD_DEPTH:
        return None
    if isinstance(node, dict):
        if "price" in node:
            price = normalize_price(node["price"])
            if price:
                return price
        for value in node.values():
            found = _find_offer_price(value, depth + 1)
            if found is not None:
                return found
    elif isinstance(node, list):
        for item in node:
            found = _find_offer_price(item, depth + 1)
            if found is not None:
                return found
    return None


@dataclass(frozen=True)
class PageRecord:
    domain: str
    url: str
    collected_at: str
    http_status: int | None
    error: str | None
    dom_price: int | None
    jsonld_price: int | None
    rendered_dom_price: int | None
    rendered_jsonld_price: int | None
    http_wall_seconds: float | None
    browser_wall_seconds: float | None

    @property
    def channels(self) -> int:
        return sum(x is not None for x in (self.dom_price, self.jsonld_price))

    @property
    def comparable(self) -> bool:
        return self.channels >= MIN_COMPARABLE_CHANNELS

    @property
    def conflict(self) -> bool:
        return self.comparable and self.dom_price != self.jsonld_price


def robots_for(domain: str) -> urllib.robotparser.RobotFileParser | None:
    parser = urllib.robotparser.RobotFileParser()
    try:
        response = httpx.get(
            f"https://{domain}/robots.txt",
            timeout=15,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT},
        )
        if response.status_code != HTTP_OK:
            return None
        parser.parse(response.text.splitlines())
        parser.set_url(f"https://{domain}/robots.txt")
        return parser
    except httpx.HTTPError:
        return None


def sitemap_candidates(domain: str, robots: urllib.robotparser.RobotFileParser) -> list[str]:
    """Product URLs from declared sitemaps, following a sitemap index one level."""
    sitemaps = list(robots.site_maps() or [])
    urls: list[str] = []
    for sitemap in sitemaps[:4]:
        body = _get_text(sitemap)
        if body is None:
            continue
        locs = re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", body)
        nested = [loc for loc in locs if loc.endswith((".xml", ".xml.gz"))]
        if nested:
            preferred = [loc for loc in nested if "product" in loc.lower()] or nested
            for child in preferred[:3]:
                child_body = _get_text(child)
                if child_body:
                    urls += [
                        loc
                        for loc in re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", child_body)
                        if not loc.endswith((".xml", ".xml.gz"))
                    ]
        else:
            urls += locs
        if len(urls) > MAX_SITEMAP_URLS:
            break
    return [u for u in urls if urlparse(u).netloc.endswith(domain.removeprefix("www."))]


def _get_text(url: str) -> str | None:
    try:
        response = httpx.get(
            url, timeout=25, follow_redirects=True, headers={"User-Agent": USER_AGENT}
        )
    except httpx.HTTPError:
        return None
    if response.status_code != HTTP_OK:
        return None
    return response.text


def write_records(records: list[PageRecord], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(asdict(record)) + "\n")


def sample_urls(domain: str, rng: random.Random) -> tuple[list[str], str | None]:
    robots = robots_for(domain)
    if robots is None:
        return [], "no_robots"
    candidates = sitemap_candidates(domain, robots)
    allowed = [u for u in candidates if robots.can_fetch(USER_AGENT, u)]
    if not allowed:
        return [], "no_sitemap_urls" if not candidates else "robots_disallow"
    rng.shuffle(allowed)
    return allowed[:MAX_ATTEMPTS_PER_DOMAIN], None


def collect() -> list[PageRecord]:
    """Fetch the sampled pages over HTTP, then render the usable ones once each."""
    rng = random.Random(SEED)
    records: list[PageRecord] = []
    plan: list[tuple[str, list[str]]] = []
    for domain in DOMAINS:
        urls, error = sample_urls(domain, rng)
        if error:
            print(f"  {domain}: skipped ({error})")
        plan.append((domain, urls))

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_context(user_agent=USER_AGENT).new_page()
        for domain, urls in plan:
            usable = 0
            for url in urls:
                if usable >= MAX_USABLE_PER_DOMAIN:
                    break
                status = error = None
                dom = jsonld = rendered_dom = rendered_jsonld = None
                http_wall = browser_wall = None
                started = time.perf_counter()
                try:
                    response = httpx.get(
                        url,
                        timeout=25,
                        follow_redirects=True,
                        headers={"User-Agent": USER_AGENT},
                    )
                    http_wall = time.perf_counter() - started
                    status = response.status_code
                    if status == HTTP_OK:
                        dom, jsonld = dom_price(response.text), jsonld_price(response.text)
                except httpx.HTTPError as exc:
                    error = type(exc).__name__

                if dom is not None or jsonld is not None:
                    usable += 1
                    started = time.perf_counter()
                    try:
                        page.goto(url, wait_until="domcontentloaded", timeout=30000)
                        page.wait_for_timeout(1200)
                        html = page.content()
                        rendered_dom, rendered_jsonld = dom_price(html), jsonld_price(html)
                    except Exception as exc:  # noqa: BLE001 - record and continue.
                        error = error or type(exc).__name__
                    browser_wall = time.perf_counter() - started

                records.append(
                    PageRecord(
                        domain=domain,
                        url=url,
                        collected_at=datetime.now(UTC).isoformat(timespec="seconds"),
                        http_status=status,
                        error=error,
                        dom_price=dom,
                        jsonld_price=jsonld,
                        rendered_dom_price=rendered_dom,
                        rendered_jsonld_price=rendered_jsonld,
                        http_wall_seconds=http_wall,
                        browser_wall_seconds=browser_wall,
                    )
                )
                time.sleep(REQUEST_SPACING_SECONDS)
            print(f"  {domain}: {usable} usable of {len(urls)} attempted")
        browser.close()
    return records
