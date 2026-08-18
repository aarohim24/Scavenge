# r/webscraping — final draft (not posted)

**Title:** I tried to deterministically reconcile web data across DOM/JSON-LD/network
responses. Real storefronts broke the semantic part, so I open-sourced the evidence layer
that survived.

---

A page usually states the same fact several times — visible HTML, JSON-LD, a hydration
blob, the rendered DOM, an XHR response — and those copies disagree more often than you'd
expect. I wanted a deterministic tool that collected all of them and told me where they
agreed and disagreed, because disagreement is where the interesting bugs are: stale
JSON-LD, prices that only exist after JS, an API that has the real number.

**Collecting them worked. Comparing them did not.**

I validated on 23 product pages across 12 storefronts, honouring robots.txt, no evasion.
Every single "these disagree" result was wrong — and none of them was a stale-price catch.
They were the product vs:

- a **second JSON-LD `Product` block** on the same page
- **£30 from a mini-cart "free delivery over £30" message**
- an **upsell tile**, and `total_price`, which is the cart, not the product
- **search-result payloads** carrying other products' availability
- **store-locator rows** with per-branch "In stock" / "Out of stock"

I added a subject-scope rule (values appearing as siblings in a JSON array, or coming from
pages that label nothing as a price, stop being page-scoped). That fixed three of those
classes and three new ones appeared. The rest need entity resolution or per-site selector
rules, so I deleted the comparison feature instead of shipping something whose headline
output is reliably wrong.

**What's left is the part that held up:**

```
$ scavenge inspect https://example.com/product/123 --field price

FIELD: price
  RAW_DOM          99.00 USD   source: div.product-price
  STRUCTURED_DATA  99.00 USD   source: script[0]/offers/price
  RENDERED_DOM     79.00 USD   source: div.product-price
  NETWORK_JSON     79.00 USD   source: GET /api/products/123  /price

ACQUISITION
  HTTP 200 · RENDER OK · JSON responses observed: 12
```

It reports what it saw and where. It does not tell you which one is right.

Two fields (`price`, `availability`), five representations, exact provenance for every value
(CSS selector, JSON pointer, or method + endpoint). CLI and an MCP server over the same
engine — one tool, `inspect_web_field(url, field)`. **No LLM anywhere in it.**

Other things that cost me real time, in case they save you some:

- `urllib.robotparser.RobotFileParser.read()` calls `urlopen()` **with no timeout**. One
  target completed the TLS handshake and never answered; it hung a run for 106 minutes.
- `&#8377;4400` parsed as the amount **8377** — the entity's own digits.
- A raw HTTP body that literally read "Are you a human?" was treated as an ordinary empty page.
- `$` is no longer assumed to be USD; it resolves from `priceCurrency`, `<html lang>` region
  or an unambiguous TLD, otherwise it stays null. Zero wrong currencies across those 23
  pages, and a lot of nulls.

Honest caveats: this is **experimental**. Two fields only. The five representations are not
equally exercised — structured data produced values in 28 of 46 runs, embedded state in 6.
23 pages is a small sample, not a benchmark. And roughly a third of the storefronts I tried
refuse robots-respecting clients outright, so the reachable population skews small and
independent.

Repo: https://github.com/aarohim24/Scavenge

```
pip install git+https://github.com/aarohim24/Scavenge.git
python -m playwright install chromium
```

**What I'd genuinely like to know:**

1. Would deterministic field-level evidence and provenance save you time when debugging or
   building scrapers, or is it a solution to a problem you don't have?
2. If you already use agents with DevTools/MCP, does this abstraction add anything, or would
   you rather hand the agent raw browser telemetry and let it figure things out?
3. **What target or page breaks it?** This is the one I care about most. I know the DOM
   fallback is naive and I know minor-unit conventions (Shopify's `2950` vs a displayed
   `29.50`) aren't modelled. I'd rather find the next class of failure from you than from
   another month of my own sampling.

The full research record, including the reports where earlier versions of this idea were
killed, is in `docs/research/` in the repo.
