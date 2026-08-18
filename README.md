# Scavenge — deterministic web evidence for humans and coding agents

`scavenge` inspects one field on one web page and reports **every place that field appears**,
what each representation says, and exactly where each value came from.

It does not tell you which value is correct. That judgement needs to know what the page
means, and this engine is deliberately incapable of it.

## What it does

```bash
$ scavenge inspect https://example.com/product/123 --field price

FIELD: price
  RAW_DOM          99.00 USD   [raw_dom:0]
                     raw:    '$99.00'
                     source: div.product-price
  STRUCTURED_DATA  99.00 USD   [structured_data:0]
                     raw:    '99.00'
                     source: script[0]/offers/price
  EMBEDDED_STATE   not observed
  RENDERED_DOM     79.00 USD   [rendered_dom:0]
                     raw:    '$79.00'
                     source: div.product-price
  NETWORK_JSON     79.00 USD   [network_json:0]
                     raw:    '79.00'
                     source: GET https://example.com/api/products/123 /price

ACQUISITION
  HTTP    200  48213 bytes  0.31s
  RENDER  OK
  JSON responses observed: 12
```

The raw HTML says 99.00, the rendered page says 79.00, and an API call explains why. You
can see that in two seconds; the engine does not assert it.

## Why it exists

A page states the same fact in several places — visible HTML, JSON-LD, a hydration blob,
the rendered DOM, an XHR response — and they disagree more often than you would like.
Working out which ones carry your field is a DevTools job, done by hand, once per target,
forever. An agent can do it too, but not reproducibly and not with exact provenance.

## Supported fields

`price` and `availability`. Two, not "arbitrary".

## Supported channels

`RAW_DOM` · `STRUCTURED_DATA` · `EMBEDDED_STATE` · `RENDERED_DOM` · `NETWORK_JSON`

**They are not equally validated.** In a 23-page validation across 12 storefronts,
`STRUCTURED_DATA` produced values in 28 of 46 runs and `EMBEDDED_STATE` in only 6.

## MCP

One tool, `inspect_web_field(url, field)`, returning structured evidence — not prose.

```json
{
  "mcpServers": {
    "scavenge": { "command": "python", "args": ["-m", "scavenge.mcp"] }
  }
}
```

The server reasons about nothing, generates no scraping code, and calls no model.

## Structured output

```json
{
  "schema_version": 3,
  "target": "https://example.com/product/123",
  "field": "price",
  "observations": [
    {
      "id": "raw_dom:0",
      "channel": "RAW_DOM",
      "normalized_value": {"kind": "money", "amount": "99.00", "currency": "USD"},
      "raw": "$99.00",
      "provenance": {"selector": "div.product-price"},
      "subject": {"scope": "PAGE", "key": "", "reason": ""},
      "status": "OK",
      "note": ""
    }
  ],
  "acquisition": {
    "http_status": 200, "http_bytes": 48213, "http_challenge": "",
    "render_status": "OK", "json_responses": 12
  },
  "warnings": []
}
```

## Architecture

```
  MCP ─┐
       ├─→ evidence engine ─→ HTTP · raw DOM · structured data
  CLI ─┘                      embedded state · rendered DOM · network JSON
```

One engine. Both interfaces call it; a test asserts the CLI's JSON is the engine's JSON.

## Install

```bash
pip install -e .
python -m playwright install chromium     # required for rendered DOM and network channels
scavenge inspect https://example.com/p/1 --field price
```

`--no-render` skips the browser and reports the HTTP-only channels.

## Security boundaries

`http`/`https` only. `file://`, localhost, loopback, link-local and private ranges are
refused before any request — which matters more under MCP, where an agent supplies URLs
without a human seeing them. Bodies capped at 512 KB, JSON responses capped at 40, bounded
waits, bounded robots fetch. robots.txt is honoured, and a timeout or unreachable
robots.txt is **never** treated as permission. No captured request is replayed, no
authenticated request reissued, nothing from a page executed.

## What it explicitly does not do

- **Decide which observation is correct.** v0.1 publishes no comparison at all.
- **Entity resolution.** It cannot reliably tell the page's product from a second Product
  block, an upsell tile, a cart total, or a store-locator row.
- Crawl, schedule, or follow links.
- Defeat anti-bot systems. It detects an obvious challenge and says so; it never bypasses one.
- Call an LLM, in any mode.

## Known limitations

1. **No comparison in v0.1.** An earlier version published `EQUAL`/`DIFFERENT` relations.
   Real-world validation found that *every* `DIFFERENT` it produced on live storefronts
   compared two different entities, so the feature was removed rather than patched. The
   full result is in [`docs/research/OSS-FINAL-CORRECTNESS.md`](docs/research/OSS-FINAL-CORRECTNESS.md).
2. **Currency is often `null`.** `$` names a dozen currencies; without declared evidence
   the amount is kept and the currency refused. Unknown is common; wrong should be absent.
3. **Minor units are not modelled** — a Shopify `2950` and a displayed `29.50` are two
   different observations.
4. **Determinism is of report generation, not of the web.** Same bytes in, same report out.
   The same URL will not always give the same bytes.
5. **A blocked render is detected only from named signals**; a thin unnamed shell is not.
6. Robots-respecting access excludes many large retailers entirely.

## License

Apache-2.0.

## Status

**Experimental v0.1.** Published for technical feedback, not for production.
The API may change. It has been validated on 23 pages across 12 storefronts, plus a
deterministic fixture suite; that is a small sample and it is not a benchmark.

The research record — including the results that killed earlier versions of this idea —
is in [`docs/research/`](docs/research/README.md).
