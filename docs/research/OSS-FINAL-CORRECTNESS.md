# Final Correctness Increment — D5 and D6

One narrow correctness pass before OSS release preparation. No features, no fields, no MCP
tools, no recommendations. Historical reports are unchanged.

---

## 1. D5 Root Cause

Two observations can carry the same field name, real values and correct provenance, and
still describe **different real-world entities**. The engine compared them anyway, so a
product price against a financing-table amount was reported `DIFFERENT` — an outright wrong
answer rather than a missing one. Observations had no notion of *subject*.

## 2. Subject Model

The smallest thing that survives the measured cases. No resolver, no graph, no matching.

```
SubjectScope  PAGE | SIBLING | UNKNOWN
Subject       scope · key · reason
```

`PAGE` — the page's own entity. `SIBLING` — one of several entries side by side in an
array, so it describes *an* entity but not necessarily the page's; `key` separates siblings.
`UNKNOWN` — no deterministic evidence either way. `reason` travels with every non-page
scope so a suppressed comparison can be explained rather than merely observed.

Assignment rules, all deterministic:

- **JSON (embedded and network):** a matching key at two or more distinct array indices
  under the same path makes each a `SIBLING`. One occurrence stays `PAGE`.
- **DOM price:** the declared labelled rule keeps `PAGE`. The unlabelled fallback — a page
  that marks *nothing* as a price — is `UNKNOWN`.
- **DOM availability:** two or more conflicting states on one page make all of them
  `UNKNOWN`.

## 3. Subject Compatibility Rules

```
PAGE   vs PAGE                  → SAME
SIBLING vs SIBLING, same key    → SAME
SIBLING vs SIBLING, other key   → DIFFERENT
PAGE   vs SIBLING               → DIFFERENT
anything vs UNKNOWN             → UNKNOWN
```

## 4. Relation Behaviour

A relation is emitted only for `SAME`. `DIFFERENT` and `UNKNOWN` emit nothing and increment
a suppression count, surfaced as one warning per report. No new relation taxonomy, no graph.

## 5. D5 Regression Results

All four named classes are covered by deterministic fixtures and pass:

| Case | Before | After |
|---|---|---|
| Financing table, no labelled price | 8 values correlated, `DIFFERENT` emitted | all `UNKNOWN`, **0 relations**, values retained |
| Financing table **with** a labelled price | — | fallback never runs; only `499.00 CAD`, `EQUAL` retained |
| Search payload, 3 other products | contradicted the page product | 3 `SIBLING`s, **no** `DIFFERENT`, page value survives |
| Store-locator rows | `In stock` vs `Out of stock` contradicted the product | all `UNKNOWN`, **0** `DIFFERENT` |
| **Retention:** same product across four channels | 3 `EQUAL` | 3 `EQUAL` — unchanged |

**A retention regression I introduced was caught and fixed during this pass.** Marking a
chosen price `UNKNOWN` merely because a page also shows related-product prices destroyed
adafruit's three correct `EQUAL` relations. `dom_prices` already selects by a declared
site-independent rule, so the chosen candidate stays `PAGE`; only a page labelling *nothing*
leaves the subject unresolved. A fixture pins this.

## 6. D6 Root Cause

`$` was mapped to USD unconditionally, so Canadian prices were labelled USD. A symbol that
names at least a dozen currencies is not evidence of one.

## 7. Currency Evidence Rules

Declared precedence, applied at the product boundary so the frozen money parser is untouched:

```
1. explicit ISO code in the value or an adjacent currency key
2. priceCurrency declared in structured data
3. <html lang> carrying a region  (en-CA → CAD, en-GB → GBP, …)
4. host TLD where the country has one unambiguous currency (.ca, .co.uk, .de, …)
5. otherwise → currency is null
```

Only the bare `$` is re-opened; `£`, `€`, `₹` keep the parser's answer. An amount with an
unknown currency is now **`UNCOMPARABLE`** against a currency-qualified one rather than
silently equal.

## 8. D6 Regression Results

Every case in the brief passes: explicit structured currency → CAD; Canadian page evidence
→ CAD; US page evidence → USD; `€499,00` → EUR; no evidence → amount kept, **currency null**;
unknown vs known → `UNCOMPARABLE`. No existing money-parser test was weakened.

## 9. Schema Changes

`schema_version` **1 → 2**, once. Observations gained a `subject` object
(`scope`, `key`, `reason`). Nothing else changed; no migration infrastructure.

## 10. Files Changed / LOC

New: `evidence/context.py` (page currency + identifiers), `tests/test_subject_and_currency.py`.
Modified: `evidence/{models,price,availability,channels,engine}.py`, `fixtures/probe/server.py`.
Production total **1,956 lines** across `evidence/` + `probe/cli.py`; this increment added
roughly **210** production lines.

## 11. Validation Population

Frozen before any engine call, and honestly narrowed as instructed: **public,
robots-accessible storefront pages reachable without authentication or anti-bot
circumvention.** Small and independent storefronts, mechanical selection (robots → homepage
200 → first product-detail path, one category hop if needed), max 2 pages per domain.
Selection never consulted relations, network JSON, or whether the engine succeeds.

## 12. Pages / Domains

**23 pages across 12 domains** (46 engine runs). 45 domains were probed; the rest were
`DISALLOWED` (8), `HTTP_403` (8), `NO_PRODUCT_LINK` (9), or robots timeout/unreachable (7).

## 13. Price Coverage

**23 of 23 pages produced at least one price value.**

## 14. Availability Coverage

**17 of 23 pages produced at least one availability value** — the first genuinely meaningful
real-world coverage this field has had.

## 15. Channel Coverage

```
observations with a value  NETWORK_JSON 109 · RAW_DOM 54 · STRUCTURED_DATA 48 ·
                           EMBEDDED_STATE 45 · RENDERED_DOM 25
runs where a channel produced a value  STRUCTURED_DATA 28 · RAW_DOM 24 · RENDERED_DOM 22 ·
                           NETWORK_JSON 14 · EMBEDDED_STATE 6      (of 46)
```

All five channels were exercised, including `EMBEDDED_STATE`, which produced nothing at all
in the previous validation.

## 16. Subject-Scope Results

```
observations by scope   PAGE 134 · SIBLING 115 · UNKNOWN 44
comparisons suppressed  236
```

Scoping is doing substantial work: 159 of 293 observations were scoped away from the page,
and 236 comparisons were refused.

## 17. Spurious Relation Rate

**16 `DIFFERENT` relations were produced. On manual adjudication, all 16 are spurious.**
Every one compares the page's product against a *different entity* that the deterministic
rules cannot recognise:

- **adafruit** — `49.95` (product) vs `5.95` from `script[1]/offers/price`, a **second
  JSON-LD Product** on the page.
- **ohmycream** — product price vs `£30` from `div.mini-cart__ksp-description`, a
  **free-delivery-threshold message in the mini-cart**. Also `6900` (pence) vs `69.0`
  (pounds), a units mismatch.
- **naturalbabyshower** — a `hasVariant/0` variant price vs `div.amp-cart__upsell-item`
  (an **upsell tile**) vs `total_price` / `items_subtotal_price` (the **cart**, not the
  product).

The three classes measured in the previous validation are fixed. Three *new* classes
appeared in their place.

## 18. Valid Relation Retention

**42 `EQUAL` relations retained**, including every correct cross-channel correlation
examined by hand. Scoping did not simply suppress everything: it removed 236 comparisons
while keeping 42 correct agreements, and the adafruit exemplar was restored after the
retention regression was caught.

## 19. Currency Results

```
.co.uk → GBP 30 · none 36
.com   → GBP 65 (declared priceCurrency) · USD 6 · none 51
```

**Known-incorrect currency assignments: 0.** Every GBP came from a declared `priceCurrency`
or a `.co.uk` host; every USD from a US-declared page; everything else was refused. D6 is
resolved: unknown is common, wrong is absent.

## 20. Defects Found During Validation

| Class | Detail | Status |
|---|---|---|
| `RELATION_ERROR` | Over-suppression: related-product prices unscoped the page's own labelled price | **Fixed**, with a fixture |
| `RELATION_ERROR` | Cross-subject relations from a second JSON-LD Product, cart/upsell DOM regions, and cart totals | **Not fixed** — see §23 |
| `NORMALIZATION_ERROR` | Shopify-style minor units (`6900` pence vs `69.0`) compared as different amounts | **Not fixed** — platform-specific |
| `OTHER` | `variant_price_font_size` matches the price key; yields `UNCOMPARABLE`, not a false value | Not fixed; harmless |

## 21. Remaining Limitations

1. **Cross-subject relations are reduced, not eliminated.** All 16 `DIFFERENT` relations in
   this run were spurious.
2. **Minor-unit conventions are not modelled**, so pence and pounds compare as different.
3. **`UNCOMPARABLE` is now the most common relation** (84), largely from amounts whose
   currency was correctly refused. Honest, but noisy.
4. Robots-respecting access still excludes most large retailers.

## 22. Quality Gate

```
before:  237 passed · ruff format clean · ruff check clean · mypy clean (54 files)
after:   250 passed · ruff format clean · ruff check clean · mypy clean (54 files)
```

## 23. Architecture Assessment

The evidence model is **not** at fault: `Subject` slotted in as three fields and one
comparison function, and the model represents every case observed. The deterministic rules
also work exactly as designed on the classes they were built for — all three D5 cases from
the previous validation are fixed and pinned by tests.

But the classes that remain need capabilities this MVP explicitly forbids:

- separating a page's Product from a second Product in another JSON-LD block needs **entity
  identity resolution**;
- recognising `div.mini-cart__ksp-description` and `amp-cart__upsell-item` as not-the-product
  needs **large selector heuristics** or semantics;
- knowing `total_price` describes the cart needs **semantic understanding of the payload**;
- pence-vs-pounds needs **platform-specific rules**.

Per the stop condition, each of those is a reason to stop rather than to build. A
conservative "subject unknown → don't correlate" was the right instinct, and it is not
sufficient: on real storefronts the page's own entity and other entities are interleaved in
ways no cheap, general, deterministic rule separated.

## 24. Final Verdict

D6 is fully resolved — zero incorrect currency assignments across 23 pages, with refusal
where evidence is absent. D5 is substantially improved: three measured failure classes fixed,
236 comparisons correctly refused, 42 valid correlations retained, zero crashes in 46 runs,
and both fields now have real coverage.

But the release gate requires spurious cross-subject relations to be **eliminated**, and
they are not: every `DIFFERENT` relation this run produced was wrong. Relations are the
differentiated primitive, so shipping an engine whose headline output is reliably wrong on
real storefronts is not defensible — and closing the remaining gap requires entity
resolution, selector heuristics or payload semantics, each of which would dissolve the
deterministic boundary that makes this product what it is.

**SUBJECT SCOPING REQUIRES TOO MUCH SEMANTICS — STOP**

What survives intact and should not be discarded: deterministic multi-channel acquisition,
exact provenance, honest currency refusal, graceful and named degradation including block
detection, and `EQUAL`/`UNCOMPARABLE` evidence — all of which held up across 46 runs. What
does not survive is the claim that the engine can tell you two representations *disagree*.
