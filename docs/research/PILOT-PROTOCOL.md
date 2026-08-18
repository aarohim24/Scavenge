# Arm E Real-World Pilot — Protocol

Frozen before any product page was fetched or any conflict computed. Nothing in this
file may change after collection begins. Arm E's algorithm is frozen as shipped in
v0.4 and is not modified by this experiment.

## Terminology correction

DOM, JSON-LD, embedded JSON and hydration state are **representation channels**, not
independent sources. They are commonly rendered from the same backend object, so
agreement between them is not independent confirmation. Arm E uses only *disagreement*
between channels as a warning signal, which is the direction that survives the loss of
independence. Earlier reports use the older wording; they are not rewritten.

## 1. Sampling methodology

1. A domain list was fixed by hand for breadth of retail category and geography before
   any page markup was inspected. No domain was chosen because of its structured data.
2. Each domain's `robots.txt` is fetched and honoured for our user agent. A domain that
   disallows the path, blocks us (401/403/429/503), or times out is recorded as a
   collection failure and skipped. No proxies, no anti-bot evasion, no authentication.
3. Product URLs come from the domain's declared XML sitemaps only. Sitemap index files
   are followed one level. A domain with no usable sitemap is skipped and recorded.
4. From the candidate URLs of each domain, a fixed-seed random sample is drawn
   (`seed = 20260817`), capped at **15 URLs per domain** so no template dominates.
5. Request rate: minimum 1.0 s between requests to the same domain.
6. Every attempted URL is recorded with its domain and collection timestamp, whether or
   not it succeeds and whether or not it supports Arm E.

**Known bias, declared in advance:** roughly half of the probed retail domains refuse
plain HTTP clients. The reachable subset therefore over-represents sites with weaker bot
protection. This pilot describes that subset, not e-commerce as a whole.

## 2. Representation channels (frozen)

Only channels the benchmark already supports:

- **DOM** — visible price text, via the existing extractor's selectors.
- **JSON_LD** — `Product`/`Offer` price in `application/ld+json`.
- **EMBEDDED_JSON** — the embedded product payload the extractor already reads.

No new channels are added to raise conflict counts.

## 3. Price semantics (frozen)

Target concept: **the current primary purchasable price presented to an ordinary
anonymous user, in the site's default locale, for the product's default variant.**

| Situation | Treatment |
|---|---|
| Sale price shown alongside struck-through list price | Sale price is the target |
| Price range (`X–Y`) for variants | AMBIGUOUS |
| Variant-specific prices, no default resolvable | AMBIGUOUS |
| Member / logged-in / coupon price | Not the target; anonymous price is |
| Subscription vs one-time price | One-time is the target; if only subscription, AMBIGUOUS |
| Multiple `offers` entries with different prices | AMBIGUOUS |
| Out of stock but price shown | Price is the target |
| Currency differs between channels | AMBIGUOUS (not a price conflict) |
| No price determinable | Excluded as unusable |

## 4. Normalization (frozen, identical to Arm E)

Digits extracted, thousands separators removed, compared as integers in minor-unit-free
form. `1999`, `"1999"` and `"1,999"` are equal. `1999` vs `2999` is a conflict. No fuzzy
or semantic matching. Values in different currencies are not compared.

## 5. Conflict definition (frozen)

A **CONFLICT** is two supported channels yielding different normalized prices for the
same semantic price field on the same page. Formatting differences are not conflicts.

## 6. Conflict taxonomy (frozen)

`STALE_STRUCTURED_DATA`, `STALE_VISIBLE_HTML`, `SALE_VS_LIST`, `VARIANT_MISMATCH`,
`LOCALIZATION`, `PERSONALIZATION`, `MULTIPLE_OFFERS`, `PARSING_ERROR`, `UNKNOWN`,
`OTHER`. Uncertain cases stay `UNKNOWN`.

## 7. Ground truth policy (frozen)

The browser result is **not** automatically truth.

- Cheap and rendered agree → the cheap record is treated as correct.
- They disagree → manually adjudicated against the rendered page's own context to
  decide which value matches the target concept, or `AMBIGUOUS`.
- Ambiguous cases are excluded from precision and reported separately.

## 8. Baselines (frozen)

- **Always HTTP** — never render.
- **Always Browser** — render every usable page.
- **Naive** — accept any complete, non-empty HTTP extraction.
- **E** — escalate on channel conflict.
- **Precedence (predeclared, not tuned): prefer the DOM price over the JSON-LD price
  whenever they disagree, and never render.** Declared before any conflict was observed.

## 9. "Materially improves correctness" (frozen)

Rendering materially improves correctness for a page iff the cheap record's price is
**not** the adjudicated true price and the rendered price **is**. Escalation that
returns the same value, or a value that is also wrong, does not count.

## 10. Cost model and minimum useful prevalence (frozen)

Measured on real pages before collection, on this machine:

```
HTTP    0.0303 CPU-seconds per page
Browser 0.1825 CPU-seconds per page      (6.0x)
Escalation surcharge = 0.1825 - 0.0303 = 0.1522 CPU-s per escalated page
```

Cost per page: always-HTTP `0.0303`; always-browser `0.1825`; E `0.0303 + p × 0.1825`.
E is cheaper than always-browser while `p < 0.834`, so on CPU alone E beats always-browser
at almost any realistic prevalence. **Cost is therefore not the binding constraint —
correctness yield is.**

The binding quantity is corrected records per 100 usable pages:
`yield = prevalence × precision`.

**Minimum useful prevalence is set at 0.02 (2%).** At the precision floor of 0.50 this
yields 1 corrected record per 100 pages, which is the smallest effect that could justify
carrying the machinery at all. Below it, E is indistinguishable from always-HTTP.

## 11. Kill criteria (committed before collection)

E dies if **any** of these fire:

1. **Precision** `< 0.50` among unambiguous E-triggered conflicts.
2. **Prevalence** `< 0.02` among pages with ≥2 comparable channels.
3. **Precedence wins** — the predeclared DOM-over-JSON-LD rule matches or beats E's
   correctness without rendering anything.
4. **Ambiguity dominates** — most conflicts are legitimately different concepts rather
   than incorrect extraction.

E continues only if conflicts are frequent enough to matter, predict cheap-extraction
risk, are resolved by rendering often enough, and are not equally handled by the
precedence rule.

## 12. No optimisation

If the data reveals a simple pattern (for example "JSON-LD is usually the stale side"),
it is reported, not implemented. Arm E is not modified by this experiment.

---

# Addendum A — Sampling-Frame Repair (frozen before any probe was run)

The instrument repair is complete and frozen. This addendum changes **only** how
product URLs are discovered and how domains qualify. Arm E's rule, the precision and
prevalence thresholds, the precedence baseline, the target price semantics, the
ambiguity rules, and the conflict taxonomy are unchanged.

## A1. Approved discovery mechanisms

1. **Sitemaps** declared in `robots.txt`, index followed one level (as before).
2. **Listing/category pages** that are publicly accessible and allowed by robots.
   Product links are taken in document order, canonicalised (scheme+host+path, query
   and fragment dropped), deduplicated, then sampled with the fixed seed.

A product link is one whose path matches the declared pattern
`/product/`, `/products/`, `/p/`, `/pdp/`, `/dp/`, `/item/`, or `-p-<digits>`.
Nothing about a page's markup, price, or channel behaviour may influence discovery.

## A2. Domain eligibility (predeclared, applied uniformly)

A domain is **ELIGIBLE** iff both hold:

1. Discovery yields **≥ 30 distinct product URLs**.
2. Of a **3-page probe**, drawn with the fixed seed from that frame and without
   inspecting any markup, **≥ 2 pages** return HTTP 200 **and** yield a chosen price in
   *both* the DOM and JSON-LD channels **with matching currency**.

`MULTIPLE_DISTINCT` does not disqualify a probe page; it is excluded later from the
prevalence denominator by the comparability rule, which is unchanged.

Dispositions recorded for every candidate: `ELIGIBLE`, `ROBOTS_DISALLOWED`,
`COLLECTION_BLOCKED`, `NO_PRODUCT_DISCOVERY`, `INSUFFICIENT_PRODUCT_URLS`,
`INSUFFICIENT_CHANNEL_COVERAGE`, `UNAVAILABLE`, `OTHER`. No candidate is dropped
silently.

## A3. Domain selection

Reconnaissance over the full candidate pool completes first. The eligible set is then
frozen and written out. Domains are selected from that frozen set with the fixed seed
(`20260817`) — never "the first five that qualify", because candidate ordering must not
determine the corpus. If few qualify, all of them are used.

Hard minimum **5 eligible domains**. No domain may exceed **25%** of usable sampled
pages; target **≤ 20 usable pages per domain** for a ~100-page pilot.

## A4. Sampling independence

Sampling may read only the frozen frame and the seed. It may not inspect conflict
status, channel agreement, whether E would trigger, browser output, ground truth, or
price structure. The recorded manifest keeps discovery and measurement in separate
passes so this separation is auditable.

## A5. Mid-pilot defect policy

If a new page exposes an extractor defect, measurement stops, affected observations are
invalidated, the defect is fixed with a preflight regression, the change is disclosed,
and the affected collection restarts cleanly. Extraction is never patched while results
continue to accumulate.
