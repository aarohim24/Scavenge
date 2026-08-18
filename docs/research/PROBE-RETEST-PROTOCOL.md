# `probe` Retest Protocol

Frozen before any retest target was drawn or inspected. One iteration only. The previous
run stands unchanged in `DIAGNOSTIC-PROTOTYPE-RESULTS.md` and is not reinterpreted.

## 1. Frozen hypothesis

> Can a local deterministic tool correlate one requested field (`price`) across raw DOM,
> structured metadata, embedded state, rendered DOM and network JSON, with exact
> provenance, more usefully than an agent manually investigating the same target?

`price` only. No new product features.

## 2. New evaluation frame — subject: single-product commerce pages

The previous frame's product-path filter mostly yielded B2B "our products" marketing
pages (`DIAGNOSTIC-PROTOTYPE-RESULTS.md` §6). The population under test is now declared:
**publicly accessible single-product commerce/PDP pages where price is a meaningful
field.**

**Source.** Tranco list `K9L5W` (2026-08-17), top 10,000 ranks, seeded shuffle
`seed = 20260819`. One target per domain, so no storefront dominates.

**Eligibility, applied in this order:**

1. robots.txt permits our user agent (bounded fetcher, `probe/robots.py`).
2. Homepage returns HTTP 200.
3. **Storefront test:** the homepage links **≥ 5 distinct product-detail paths** — a path
   matching the frozen pattern (`/product/`, `/products/`, `/p/`, `/pdp/`, `/dp/`,
   `/item/`, `-p-<digits>`) **followed by at least one further non-empty segment**. The
   trailing segment is what distinguishes a product page from a `/products/` index, which
   is the exact confusion that spoiled the previous frame.
4. Target = the first such link in homepage document order, robots-permitted.
5. **Price-concept test:** the **rendered** page contains a currency symbol adjacent to
   digits.

**Why step 5 is checked on the rendered page.** Establishing that a price exists at all is
the declared subject of the population. Checking it after rendering is the most inclusive
possible test, so a page whose price appears only after JavaScript still qualifies.
Checking the raw body instead would have quietly excluded exactly the client-rendered
cases the diagnostic exists to detect, and biased the run toward easy HTTP-sufficient
answers.

**Forbidden as selection inputs, unchanged:** whether `probe` succeeds; JSON-LD presence;
network-endpoint presence; raw/rendered disagreement; representation count; whether
browser rendering is needed. Steps 3 and 5 read a URL path and the presence of any price
anywhere — never a channel, never a comparison, never a recommendation.

**Ten targets. No scaling.** Every rejection recorded with its reason.

## 3. Order of investigation

Per target, and never reversed: **agent-manual investigation first, then `probe`.**
Human DevTools remains **UNMEASURED**. Agent + `chrome-devtools-mcp` remains
**QUALITATIVE** unless actually executed.

## 4. Kill criteria (predeclared; not altered after results)

Any one of these kills the standalone diagnostic:

1. **Reliability** — `probe` crashes on even **1 of 10** targets from an ordinary page or
   network condition that should have degraded gracefully.
2. **Field recall** — on **2 or more** targets the agent-manual pass finds the price
   straightforwardly while `probe` reports no usable price evidence.
3. **Misleading advice** — **2 or more** recommendations suggest a cheaper extraction path
   that does not actually carry the field.
4. **Usefulness** — on **fewer than 5 of 10** targets, `probe` automatically surfaces at
   least one genuinely useful piece of evidence the agent would otherwise have had to find
   by hand: exact field provenance, a useful correlated JSON endpoint, a meaningful
   raw-vs-rendered change, a representation disagreement, or evidence that rendering
   leaves the field unchanged.
5. **Agent comparison** — if the measured agent-manual workflow remains clearly faster and
   more complete overall and `probe`'s deterministic evidence does not materially reduce
   investigation work.

## 5. Two outcomes measured separately

**Evidence acquisition** is scored apart from **recommendation quality**. `probe` is not
required to out-reason an agent; its candidate advantage is deterministic, provenance-
carrying evidence. If the evidence engine proves useful while the standalone CLI does not,
that is a first-class result and will be reported as such.

## 6. Alternative product form

Evaluated from results only, not implemented: would this be more valuable as an
MCP/tool primitive handing deterministic evidence to an agent than as a standalone CLI
competing with one?

## 7. Novelty discipline

Unchanged. Never claimed: browser automation, endpoint discovery, structured-data
inspection, raw-vs-rendered comparison. The surviving primitive is **deterministic
field-level value correlation with provenance across representation channels**.

## 8. No third rescue iteration

If the repaired prototype fails this test, the result is accepted.
