"""Product-URL discovery and domain eligibility, per PILOT-PROTOCOL.md Addendum A.

Two approved mechanisms: declared sitemaps, and product links read from publicly
accessible listing pages. Discovery never inspects markup, prices, or channel
behaviour — only URL shape — so sampling cannot select for disagreement.
"""

from __future__ import annotations

import re
import urllib.robotparser
from urllib.parse import urljoin, urlparse

from selectolax.parser import HTMLParser

from realworld.collect import USER_AGENT, PoliteFetcher

PRODUCT_PATH = re.compile(r"/products?/|/p/|/pdp/|/dp/|/item/|-p-\d+", re.IGNORECASE)
LISTING_PATH = re.compile(r"/collections?/|/category/|/categories/|/c/|/shop/|/catalog", re.I)
MIN_PRODUCT_URLS = 30
PROBE_SIZE = 3
PROBE_PASS = 2
_MAX_SITEMAPS = 3
_MAX_SITEMAP_CHILDREN = 4
_MAX_LISTING_PAGES = 4
_URL_BUDGET = 3000


def canonical(url: str) -> str:
    """Scheme, host and path only. Query and fragment are dropped before dedup."""
    parts = urlparse(url)
    return f"{parts.scheme}://{parts.netloc}{parts.path}".rstrip("/")


def _locs(body: str) -> list[str]:
    return re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", body)


def from_sitemaps(robots: urllib.robotparser.RobotFileParser, fetcher: PoliteFetcher) -> list[str]:
    urls: list[str] = []
    for sitemap in list(robots.site_maps() or [])[:_MAX_SITEMAPS]:
        outcome = fetcher.get(sitemap)
        if not outcome.ok or outcome.body is None:
            continue
        locations = _locs(outcome.body)
        nested = [loc for loc in locations if loc.endswith((".xml", ".xml.gz"))]
        if not nested:
            urls += locations
        else:
            preferred = [n for n in nested if re.search(r"produkt|product|item", n, re.I)]
            for child in (preferred or nested)[:_MAX_SITEMAP_CHILDREN]:
                child_outcome = fetcher.get(child)
                if child_outcome.ok and child_outcome.body:
                    urls += [
                        loc
                        for loc in _locs(child_outcome.body)
                        if not loc.endswith((".xml", ".xml.gz"))
                    ]
        if len(urls) > _URL_BUDGET:
            break
    return urls


def from_listing_pages(domain: str, fetcher: PoliteFetcher) -> list[str]:
    """Product links read in document order from the homepage and a few listing pages."""
    home = fetcher.get(f"https://{domain}/")
    if not home.ok or home.body is None:
        return []

    def links(html: str, base: str) -> list[str]:
        return [
            urljoin(base, node.attributes.get("href") or "")
            for node in HTMLParser(html).css("a[href]")
        ]

    base = f"https://{domain}/"
    found = links(home.body, base)
    urls = [u for u in found if PRODUCT_PATH.search(urlparse(u).path)]

    listings = [u for u in found if LISTING_PATH.search(urlparse(u).path)]
    for listing in listings[:_MAX_LISTING_PAGES]:
        outcome = fetcher.get(listing)
        if outcome.ok and outcome.body:
            urls += [
                u for u in links(outcome.body, listing) if PRODUCT_PATH.search(urlparse(u).path)
            ]
    return urls


def discover(
    domain: str, robots: urllib.robotparser.RobotFileParser, fetcher: PoliteFetcher
) -> tuple[list[str], str]:
    """Product URLs for a domain, plus which mechanism produced them."""
    host = domain.removeprefix("www.")
    seen: dict[str, None] = {}
    method = "sitemap"

    for source, name in (
        (from_sitemaps(robots, fetcher), "sitemap"),
        (from_listing_pages(domain, fetcher), "listing"),
    ):
        for url in source:
            if not PRODUCT_PATH.search(urlparse(url).path):
                continue
            if not urlparse(url).netloc.endswith(host):
                continue
            if not robots.can_fetch(USER_AGENT, url):
                continue
            seen.setdefault(canonical(url))
        if len(seen) >= MIN_PRODUCT_URLS:
            method = name if not seen else method if name == "listing" else name
            break
        method = name

    return list(seen), method
