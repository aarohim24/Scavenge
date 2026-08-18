"""Deterministic fixture server for the `probe` prototype.

Unlike the benchmark's fixture server, these pages must be able to make network
requests, because the network channel is the thing under test. Pages and JSON
endpoints are declared together here so a reader can see, for one case, exactly what
the raw body contains and what the page fetches.

Only the seven logical cases PROBE-PROTOCOL.md §24 requires. No page exists to make a
recommendation look good.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

HOST = "127.0.0.1"

# `lang` carries a region because "$" alone no longer implies USD: the fixtures must
# state their own locale, exactly as a real page has to.
_HEAD = '<!doctype html><html lang="en-US"><head><meta charset="utf-8"><title>{t}</title>'


def _client_replace(selector: str, text: str, fetch: str | None = None) -> str:
    """Rewrites an element after load, optionally from a fetched endpoint."""
    if fetch is None:
        return (
            "<script>window.addEventListener('DOMContentLoaded',()=>{"
            f"document.querySelector('{selector}').textContent={text!r};"
            "});</script>"
        )
    return (
        "<script>window.addEventListener('DOMContentLoaded',()=>{"
        f"fetch('{fetch}').then(r=>r.json()).then(d=>{{"
        f"document.querySelector('{selector}').textContent='$'+d.price;"
        "});});</script>"
    )


PAGES: dict[str, str] = {
    # 1. HTTP sufficient: the price is in the raw body and nothing changes it.
    "/http-sufficient": _HEAD.format(t="Kettle") + "</head><body>"
    '<h1>Kettle</h1><span class="price">$24.00</span>'
    "</body></html>",
    # 2. Rendering changes the field, and no endpoint explains it.
    "/render-changes-field": _HEAD.format(t="Lamp")
    + _client_replace("span.price", "$19.00")
    + "</head><body>"
    '<h1>Lamp</h1><span class="price">$29.00</span>'
    "</body></html>",
    # 3. A JSON endpoint supplies the rendered value.
    "/endpoint-matches-rendered": _HEAD.format(t="Desk")
    + _client_replace("span.price", "", fetch="/api/desk")
    + "</head><body>"
    '<h1>Desk</h1><span class="price">$99.00</span>'
    "</body></html>",
    # 4. A JSON request that has nothing to do with the field.
    "/irrelevant-json": _HEAD.format(t="Chair")
    + "<script>window.addEventListener('DOMContentLoaded',()=>{fetch('/api/telemetry');});</script>"
    + "</head><body>"
    '<h1>Chair</h1><span class="price">$45.00</span>'
    "</body></html>",
    # 5. Several endpoints, only one of which carries the field.
    "/multiple-endpoints": _HEAD.format(t="Shelf")
    + "<script>window.addEventListener('DOMContentLoaded',()=>{"
    "fetch('/api/telemetry');fetch('/api/reviews');"
    "fetch('/api/shelf').then(r=>r.json()).then(d=>{"
    "document.querySelector('span.price').textContent='$'+d.price;});});</script>" + "</head><body>"
    '<h1>Shelf</h1><span class="price">$10.00</span>'
    "</body></html>",
    # 6. Client-rendered with no useful endpoint: the browser is genuinely required.
    "/no-useful-endpoint": _HEAD.format(t="Rug")
    + "<script>window.addEventListener('DOMContentLoaded',()=>{"
    "document.getElementById('app').innerHTML="
    "'<span class=\"price\">$61.00</span>';});</script>" + "</head><body>"
    '<h1>Rug</h1><div id="app"></div>'
    "</body></html>",
    # 8. Polls forever, so networkidle never arrives. The price is plainly present.
    "/never-idle": _HEAD.format(t="Fan")
    + "<script>setInterval(()=>{fetch('/api/telemetry');},300);</script>"
    + "</head><body>"
    '<h1>Fan</h1><span class="price">$33.00</span>'
    "</body></html>",
    # 9. No element is marked as a price; the amount is only in element text.
    "/unlabelled-price": _HEAD.format(t="Stool") + "</head><body>"
    '<h1>Stool</h1><span class="a7f3b">$42.00</span>'
    "</body></html>",
    # 10. Two unlabelled amounts: ambiguity, not an arbitrary pick.
    "/unlabelled-two-prices": _HEAD.format(t="Tiers") + "</head><body>"
    '<h1>Tiers</h1><span class="a7f3b">$9.00</span><span class="b2c1d">$19.00</span>'
    "</body></html>",
    # 11. Prose containing a currency amount that is not a price.
    "/currency-in-prose": _HEAD.format(t="Policy") + "</head><body>"
    "<h1>Policy</h1><p>Single domain requiring full EV vetting and $1.75M warranty</p>"
    "</body></html>",
    # 12. The MVP integration page: two fields, four channels, deliberate disagreement.
    #     No representation is truth; the fixture tests correlation, not correctness.
    "/integration": _HEAD.format(t="Kit")
    + '<script type="application/ld+json">'
    + json.dumps(
        {
            "@type": "Product",
            "name": "Kit",
            "offers": {
                "price": "99.00",
                "priceCurrency": "USD",
                "availability": "https://schema.org/InStock",
            },
        }
    )
    + "</script>"
    + "<script>window.addEventListener('DOMContentLoaded',()=>{"
    "fetch('/api/kit').then(r=>r.json()).then(d=>{"
    "document.querySelector('span.price').textContent='$'+d.price;"
    "document.querySelector('span.stock').textContent='Sold out';});});</script>" + "</head><body>"
    '<h1>Kit</h1><span class="price">$99.00</span><span class="stock">In stock</span>'
    "</body></html>",
    # 13. Raw HTTP serves the product; the browser is shown a Cloudflare interstitial.
    #     The engine must not read a price out of the challenge page.
    "/blocked-render": _HEAD.format(t="Blocked")
    + "<script>window.addEventListener('DOMContentLoaded',()=>{"
    "document.body.innerHTML='<h1>Just a moment...</h1>"
    "<p>Checking your browser before accessing the site.</p>"
    "<div class=\\'price\\'>$1.00</div>';});</script>" + "</head><body>"
    '<h1>Blocked</h1><span class="price">$55.00</span>'
    "</body></html>",
    # 14. A captcha widget on a page that is otherwise empty.
    "/captcha-wall": _HEAD.format(t="Verify") + "</head><body>"
    '<div class="g-recaptcha" data-sitekey="x"></div>'
    "</body></html>",
    # 15. A checkout-style page that legitimately carries a captcha AND real content.
    "/captcha-with-content": _HEAD.format(t="Checkout") + "</head><body>"
    '<h1>Checkout</h1><span class="price">$76.00</span>'
    "<p>" + ("Complete your order below. " * 20) + "</p>"
    '<div class="g-recaptcha" data-sitekey="x"></div>'
    "</body></html>",
    # 16. The raw HTTP response is itself a bot check; the price in it is not the product's.
    "/blocked-http": _HEAD.format(t="Verify") + "</head><body>"
    "<h1>Are you a human?</h1>"
    '<span class="price">$1.00</span>'
    "</body></html>",
    # 17. Boolean flags whose keys match the price pattern. Never amounts.
    "/boolean-price-flags": _HEAD.format(t="Flags")
    + '<script type="application/json" id="__STATE__">'
    + json.dumps({"price": "27.50", "isClubPrice": False, "isOutletPrice": False})
    + "</script></head><body>"
    "<h1>Flags</h1>"
    "</body></html>",
    # 18. D5 — a financing table and no labelled price, reproducing canadiantire.ca.
    "/financing-table": _HEAD.format(t="Dehumidifier") + "</head><body>"
    "<h1>Dehumidifier</h1>"
    "<table><tr><td>$100</td><td>$1.81</td></tr><tr><td>$500</td><td>$9.04</td></tr>"
    "<tr><td>$1000</td><td>$18.07</td></tr><tr><td>$2000</td><td>$36.15</td></tr></table>"
    "</body></html>",
    # 19. D5 — the same financing table, but the product price is labelled.
    "/financing-with-labelled-price": _HEAD.format(t="Dehumidifier")
    + '<script type="application/ld+json">'
    + json.dumps({"@type": "Product", "offers": {"price": "499.00", "priceCurrency": "CAD"}})
    + "</script></head><body>"
    '<h1>Dehumidifier</h1><span class="price">$499.00</span>'
    "<table><tr><td>$100</td><td>$1.81</td></tr><tr><td>$2000</td><td>$36.15</td></tr></table>"
    "</body></html>",
    # 20. D5 — a search payload carrying other products' availability, reproducing lakeland.
    "/search-payload": _HEAD.format(t="Pan")
    + '<script type="application/ld+json">'
    + json.dumps({"@type": "Product", "offers": {"availability": "https://schema.org/InStock"}})
    + "</script>"
    + "<script>window.addEventListener('DOMContentLoaded',()=>{fetch('/api/search');});</script>"
    + "</head><body><h1>Pan</h1></body></html>",
    # 21. D5 — store-locator rows, reproducing the naturisimo case.
    "/store-locator": _HEAD.format(t="Powder")
    + '<script type="application/ld+json">'
    + json.dumps({"@type": "Product", "offers": {"availability": "https://schema.org/InStock"}})
    + "</script></head><body><h1>Powder</h1>"
    '<div class="location-list-item__stock">In stock</div>'
    '<div class="location-list-item__stock">Out of stock</div>'
    '<div class="location-list-item__stock">In stock</div>'
    "</body></html>",
    # 22. D6 — a bare "$" on a page whose locale says Canada.
    "/canadian-price": '<!doctype html><html lang="en-CA"><head><meta charset="utf-8">'
    "<title>CA</title></head><body>"
    '<h1>CA</h1><span class="price">$499.00</span>'
    "</body></html>",
    # 23. D6 — a bare "$" with no locale evidence at all.
    "/no-locale-price": '<!doctype html><html><head><meta charset="utf-8">'
    "<title>None</title></head><body>"
    '<h1>None</h1><span class="price">$499.00</span>'
    "</body></html>",
    # 24. D6 — an unambiguous symbol needs no page evidence.
    "/euro-price": '<!doctype html><html><head><meta charset="utf-8">'
    "<title>EU</title></head><body>"
    '<h1>EU</h1><span class="price">&euro;499,00</span>'
    "</body></html>",
    # 25. Related-product prices alongside the product's own labelled price (adafruit shape).
    "/neighbouring-prices": _HEAD.format(t="Board")
    + '<script type="application/ld+json">'
    + json.dumps({"@type": "Product", "offers": {"price": "49.95", "priceCurrency": "USD"}})
    + "</script></head><body>"
    '<h1>Board</h1><p class="price">$49.95</p>'
    '<aside><p class="price">$12.50</p><p class="price">$7.00</p></aside>'
    "</body></html>",
    # 7. Two cheap representations of the same field that disagree.
    "/representations-disagree": _HEAD.format(t="Mug")
    + '<script type="application/ld+json">'
    + json.dumps(
        {"@type": "Product", "name": "Mug", "offers": {"price": "12.00", "priceCurrency": "USD"}}
    )
    + "</script></head><body>"
    '<h1>Mug</h1><span class="price">$18.00</span>'
    "</body></html>",
}

ENDPOINTS: dict[str, dict[str, Any]] = {
    "/api/desk": {"sku": "desk-1", "price": "79.00", "currency": "USD"},
    "/api/shelf": {"sku": "shelf-1", "price": "8.50", "currency": "USD"},
    "/api/kit": {"sku": "kit-1", "price": "79.00", "currency": "USD", "availability": "InStock"},
    "/api/search": {
        "results": [
            {
                "hits": [
                    {"sku": "a", "availability": "https://schema.org/OutOfStock"},
                    {"sku": "b", "availability": "https://schema.org/InStock"},
                    {"sku": "c", "availability": "https://schema.org/OutOfStock"},
                ]
            }
        ]
    },
    "/api/telemetry": {"session": "abc", "events": 3},
    "/api/reviews": {"count": 12, "average": 4.5},
}


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler's interface
        if self.path in PAGES:
            self._send(PAGES[self.path].encode(), "text/html; charset=utf-8")
        elif self.path in ENDPOINTS:
            self._send(json.dumps(ENDPOINTS[self.path]).encode(), "application/json")
        elif self.path == "/robots.txt":
            self._send(b"User-agent: *\nAllow: /\n", "text/plain")
        else:
            self.send_error(404)

    def _send(self, body: bytes, content_type: str) -> None:
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002, ARG002 - stdlib signature
        """Silent: request logs would bury the test output."""


@contextmanager
def probe_fixture_server() -> Iterator[str]:
    server = ThreadingHTTPServer((HOST, 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://{HOST}:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
