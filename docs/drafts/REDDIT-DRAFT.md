# r/webscraping draft — not posted

**Title:** I tried deterministic cross-representation correlation. Real storefronts broke
the semantic half, so I open-sourced the evidence layer that survived.

---

The idea was: a page states a price in several places — visible HTML, JSON-LD, a hydration
blob, the rendered DOM, an XHR response — so collect all of them, normalise the values, and
report where they agree and disagree. Disagreement is where the interesting bugs live
(stale JSON-LD, prices that only appear after JS, an API that has the real number).

Collecting them worked. **Comparing them did not**, and I want to be specific about how it
failed, because I don't think it's obvious.

I validated on 23 product pages across 12 storefronts, honouring robots, no evasion. Every
`DIFFERENT` relation the engine produced was wrong. Not one of them was a stale-price catch.
They were:

- the page's product vs a **second JSON-LD Product block** on the same page
- the product price vs **`£30` from a mini-cart "free delivery over £30" message**
- a variant price vs an **upsell tile** vs **`total_price`** — which is the cart, not the product
- search-results payloads carrying **other products'** availability
- **store-locator rows** with per-branch "In stock" / "Out of stock"

I added a subject-scope rule (values appearing as siblings in a JSON array, or from pages
that label nothing as a price, stop being page-scoped). That fixed three of those classes,
and three new ones appeared. The remainder need entity resolution or a pile of per-site
selector rules. So I removed comparison from the public API rather than shipping something
whose headline output is reliably wrong.

What's left, and what I actually shipped:

- one field at a time (`price` or `availability`), across raw DOM / structured data /
  embedded state / rendered DOM / network JSON
- exact provenance for every value: CSS selector, JSON pointer, or method + endpoint URL
- normalised money with **no currency guessing** — `$` resolves from `priceCurrency`,
  `<html lang>` region, or unambiguous TLD, otherwise it stays null. Zero wrong currencies
  across the validation set; plenty of nulls.
- bounded rendering that degrades into named states instead of crashing
  (`PARTIAL_RENDER`, `RENDERING_TIMEOUT`, `BLOCKED_OR_CHALLENGED`) — the block detection is
  detection only, it bypasses nothing
- CLI + MCP over the same engine, no LLM anywhere

Other things that went wrong, since they cost me real time and might save you some:

- `urllib.robotparser.RobotFileParser.read()` calls `urlopen()` **with no timeout**. One
  target accepted the TLS handshake and never answered; it hung a run for 106 minutes.
- `&#8377;4400` parsed as the amount **8377** — the entity's own digits.
- Shopify-style state gave me `price: 2950` (pence) next to a displayed `29.50`, and a
  `variant_price_font_size: 14` that matched my price key.
- A raw HTTP body that literally read "Are you a human?" was treated as an ordinary empty page.

Caveats: two fields only, five channels that are far from equally exercised, 23 pages is a
small sample, and roughly a third of the storefronts I tried refuse robots-respecting
clients outright, so the reachable population skews small and independent.

**What I'd like to know:** for those of you maintaining scrapers at any scale — is a
"here's every place this field appears, with provenance, no opinion" report useful to you,
or is the opinion the whole point? And has anyone found a deterministic way to scope "this
page's product" that doesn't turn into per-site rules? That's the wall I hit.
