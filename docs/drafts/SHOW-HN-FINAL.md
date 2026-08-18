# Show HN — final draft (not posted)

**Title:** Show HN: Scavenge – deterministic web evidence for coding agents

**URL:** https://github.com/aarohim24/Scavenge

---

Agents are good at interpreting a web page. They're less good at collecting the same
evidence twice and telling you where it came from.

Scavenge is the deterministic half. You give it a URL and a field; it reports every place
that field appears — visible HTML, JSON-LD, embedded state, the rendered DOM, and JSON the
page fetched — with the exact selector, JSON pointer, or endpoint each value came from.

```
$ scavenge inspect https://example.com/product/123 --field price

FIELD: price
  RAW_DOM          99.00 USD   source: div.product-price
  STRUCTURED_DATA  99.00 USD   source: script[0]/offers/price
  RENDERED_DOM     79.00 USD   source: div.product-price
  NETWORK_JSON     79.00 USD   source: GET /api/products/123  /price
```

It does not tell you which value is correct.

That's a measured decision, not modesty. An earlier version compared observations and
published EQUAL/DIFFERENT. I validated it on 23 pages across 12 storefronts and every
DIFFERENT it produced was wrong — not because the values or provenance were wrong, but
because the two observations described different things: a second Product block on the page,
a mini-cart "free delivery over £30" message, an upsell tile, a cart total. Telling those
apart is entity resolution, which would dissolve the only property that makes the tool worth
having. So I removed the comparison and shipped the layer underneath it.

There's a CLI and an MCP server over the same engine — one tool,
`inspect_web_field(url, field)`, returning structured evidence rather than prose. **No model
is called anywhere in it.** Related: `$` is no longer assumed to be USD; currency resolves
from declared evidence or stays null.

Scope, honestly: two fields (price, availability), five representations that are not equally
exercised, 23 pages is a small sample and not a benchmark, and robots-respecting access
excludes many large retailers. It's experimental and the API may change. The research record
in the repo includes the reports where earlier versions of this idea were killed.

The question I'd most like answered:

**Is deterministic field-level web evidence useful enough to deserve a separate tool, or
would you rather let an agent inspect DevTools directly?**
