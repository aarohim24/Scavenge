"""Deterministic local fixture server.

Serves `fixtures/pages/<name>.html` at `/<name>`. No network access, no clock
dependence, no randomness — a benchmark that measured site variance would be
measuring the wrong thing.
"""

from __future__ import annotations

import re
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

HOST = "127.0.0.1"
PAGES_DIR = Path(__file__).parent / "pages"
GROUND_TRUTH_PATH = Path(__file__).parent / "ground_truth.json"

_FIXTURE_NAME = re.compile(r"[a-z0-9-]+")
_FAMILY_MEMBER = re.compile(r"([a-z]+)/([0-9]+)")

# Family pages share a URL template so Crawlee's rendering predictor has something
# to generalise from; the v0.1 island fixtures give it nothing. They are rendered
# from these templates rather than copied to disk nine times. Nothing in the URL
# encodes which execution mode a page needs.
_SERVER_RENDERED = """<!doctype html>
<html lang="en"><head><meta charset="utf-8" /><title>{name}</title>
<script>window.__CRAWLBENCH_READY = true;</script></head>
<body><main><h1 class="product-title">{name}</h1>
<span class="price" data-currency="INR">&#8377;{price}</span></main></body></html>
"""

_CLIENT_RENDERED = """<!doctype html>
<html lang="en"><head><meta charset="utf-8" /><title>{name}</title>
<script>
  window.__CRAWLBENCH_READY = false;
  window.addEventListener("DOMContentLoaded", () => {{
    document.getElementById("app").innerHTML =
      '<h1 class="product-title">{name}</h1>' +
      '<span class="price" data-currency="INR">&#8377;{price}</span>';
    window.__CRAWLBENCH_READY = true;
  }});
</script></head>
<body><main><div id="app"></div></main></body></html>
"""

# Ships a pre-discount price and applies the active promotion in the browser.
_CLIENT_DISCOUNTED = """<!doctype html>
<html lang="en"><head><meta charset="utf-8" /><title>{name}</title>
<script>
  window.__CRAWLBENCH_READY = false;
  window.addEventListener("DOMContentLoaded", () => {{
    document.querySelector("span.price").textContent = "₹{price}";
    window.__CRAWLBENCH_READY = true;
  }});
</script></head>
<body><main><h1 class="product-title">{name}</h1>
<span class="price" data-currency="INR">&#8377;{list_price}</span></main></body></html>
"""

# (template, name, rendered price, pre-render price where the two differ)
_FAMILY_PAGES: dict[str, tuple[str, str, int, int | None]] = {
    "products/101": (_SERVER_RENDERED, "Aurora Desk Lamp", 1899, None),
    "products/102": (_SERVER_RENDERED, "Cedar Bookend Pair", 1299, None),
    "products/103": (_SERVER_RENDERED, "Linen Throw Blanket", 2499, None),
    "listings/201": (_CLIENT_RENDERED, "Harbour View Loft", 4500, None),
    "listings/202": (_CLIENT_RENDERED, "Garden Studio Flat", 3800, None),
    "listings/203": (_CLIENT_RENDERED, "Riverside Two-Bed", 5200, None),
    "deals/301": (_SERVER_RENDERED, "Winter Bundle", 999, None),
    "deals/302": (_SERVER_RENDERED, "Desk Refresh Bundle", 1499, None),
    "deals/303": (_CLIENT_DISCOUNTED, "Flash Hour Bundle", 1799, 2599),
}


# Reference pages for the RAPTURE-style verifier (arm E0). Generation rule, declared
# before generating and applied to the whole set: twelve server-rendered product pages
# whose names alternate between two and three words and whose prices step by 250 from
# 1000. They are not benchmark tasks and have no ground-truth entry; they exist only to
# supply "previously verified" extractions for the verifier to fit.
_REFERENCE_NAMES = (
    "Copper Kettle",
    "Walnut Cutting Board",
    "Ceramic Mug",
    "Brushed Steel Ladle",
    "Cotton Apron",
    "Folding Camp Stool",
    "Glass Carafe",
    "Woven Storage Basket",
    "Bamboo Tray",
    "Enamel Coffee Pot",
    "Marble Coaster",
    "Cast Iron Skillet",
)
REFERENCE_PATHS = tuple(f"/reference/{501 + index}" for index in range(len(_REFERENCE_NAMES)))

_REFERENCE_PAGES: dict[str, tuple[str, str, int, int | None]] = {
    f"reference/{501 + index}": (_SERVER_RENDERED, name, 1000 + 250 * index, None)
    for index, name in enumerate(_REFERENCE_NAMES)
}

_PARAMETERIZED_PAGES = {**_FAMILY_PAGES, **_REFERENCE_PAGES}


def render_family_page(member: str) -> str:
    template, name, price, list_price = _PARAMETERIZED_PAGES[member]
    return template.format(name=name, price=price, list_price=list_price)


class _FixtureHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_GET(self) -> None:  # noqa: N802  # http.server's required spelling.
        name = self.path.lstrip("/").split("?", 1)[0]

        if _FAMILY_MEMBER.fullmatch(name):
            if name not in _PARAMETERIZED_PAGES:
                self.send_error(404, "no such family page")
                return
            body = render_family_page(name).encode("utf-8")
        else:
            # Reject anything that is not a bare fixture name; this also rules out
            # path traversal into the rest of the repository.
            if not _FIXTURE_NAME.fullmatch(name):
                self.send_error(404, "not a fixture")
                return

            page = PAGES_DIR / f"{name}.html"
            if not page.is_file():
                self.send_error(404, "no such fixture")
                return

            body = page.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        """Silence per-request logging so benchmark output stays readable."""


@contextmanager
def serve_fixtures() -> Iterator[str]:
    """Run the fixture server on an ephemeral port; yield its base URL."""
    server = ThreadingHTTPServer((HOST, 0), _FixtureHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        # Only the port is dynamic; the host is the loopback address we bound to.
        port = int(server.server_address[1])
        yield f"http://{HOST}:{port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
