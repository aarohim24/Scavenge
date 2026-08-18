# Show HN draft — not posted

**Title:** Show HN: Scavenge – deterministic web evidence for coding agents

---

I kept watching agents (and myself) do the same thing on an unfamiliar page: open DevTools,
check view-source, check the JSON-LD, check the Network tab, and work out where a value
actually lives. It's the same job every time, it isn't reproducible, and when an agent does
it you get an answer without provenance.

So this does the acquisition deterministically and hands back the evidence:

    $ scavenge inspect https://example.com/product/123 --field price

    FIELD: price
      RAW_DOM          99.00 USD   source: div.product-price
      STRUCTURED_DATA  99.00 USD   source: script[0]/offers/price
      RENDERED_DOM     79.00 USD   source: div.product-price
      NETWORK_JSON     79.00 USD   source: GET /api/products/123 /price

It's a CLI and an MCP server over one engine — one tool, `inspect_web_field(url, field)`.
No model is called anywhere in it.

**What it deliberately does not do:** tell you which value is correct.

That's not modesty, it's a measured result. An earlier version published `EQUAL` /
`DIFFERENT` relations between observations. I validated it on 23 pages across 12
storefronts and **every single `DIFFERENT` it produced was wrong** — not because the values
or provenance were wrong, but because the two observations described different *entities*:
a second JSON-LD Product on the page, a mini-cart "free delivery over £30" message, an
upsell tile, a cart total. Telling those apart needs entity resolution or a pile of
selector heuristics, which would dissolve the only property that makes this thing worth
having. So I deleted the comparison feature and shipped the layer underneath it.

Related: `$` is no longer assumed to be USD. It resolves from declared evidence
(`priceCurrency`, `<html lang>` region, unambiguous host TLD) or stays null. Across those
23 pages, zero incorrect currency assignments — and a lot of nulls.

Honest scope: two fields (`price`, `availability`), five channels that are **not** equally
validated (structured data produced values in 28 of 46 runs; embedded state in 6), 23 pages
is a small sample and not a benchmark, and robots-respecting access excludes most large
retailers — about a third of the domains I tried simply refuse.

I'm not claiming the pieces are novel. Structured-data extraction, XHR capture and
raw-vs-rendered diffing all have prior art, and there are good tools nearby. What I haven't
found elsewhere is the deterministic, provenance-carrying, field-level version of it that
an agent can call and a human can diff.

**Feedback I'd actually like:**

1. Is a report with no comparison in it still useful to you, or did I cut the only
   interesting part?
2. Is per-observation subject scope (`PAGE` / `SIBLING` / `UNKNOWN`) the right shape, given
   I won't do entity resolution?
3. Where does the currency precedence break — I expect it does, somewhere I haven't looked.
4. If you run agents against the web: would you rather have this as an MCP tool, or as a
   library your own tooling calls?

The full research record is in the repo, including the reports where earlier versions of
this idea were killed.
