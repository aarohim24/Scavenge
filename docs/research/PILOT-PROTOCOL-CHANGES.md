# Instrument Repair — Changes After the Invalid Pilot

Every methodological and code change made after the pilot was declared invalid, and
which of them were informed by seeing pilot data. Arm E's hypothesis, mechanism, kill
criteria, minimum-useful-prevalence threshold, and the benchmark's semantics are
**unchanged**. The invalid pilot's numbers are not reinterpreted as evidence about E.

## Unchanged (frozen)

- Arm E's rule: reject on missing required field or cross-channel disagreement.
- Kill criteria: precision < 0.50; prevalence < 0.02; precedence rule wins; ambiguity
  dominates.
- Minimum useful prevalence 0.02, derived from the pre-collection cost measurement
  (HTTP 0.0303 CPU-s, browser 0.1825 CPU-s per page).
- Predeclared precedence baseline: prefer DOM over JSON-LD, never render.
- Target price concept, ambiguity rules, and conflict taxonomy in `PILOT-PROTOCOL.md`.
- All benchmark arms A/B/C/D1/D2/E0 and their reported results.

## Changed, with disclosure

| # | Change | Informed by pilot data? |
|---|---|---|
| 1 | Monetary values are `Decimal` + currency, never `int`/`float`. Separator conventions resolved from currency, then page language; insufficient evidence returns `AMBIGUOUS_SEPARATOR` rather than a guess. | Yes — the `3,99€ → 3` and `3.99 → 4` failures were found in pilot output. |
| 2 | DOM selection rule replaced. Old: skip any price-labelled element containing another; that discarded every element holding a number (0 prices on 55 pages). New: keep all candidates with provenance, drop superseded prices (struck-through, "was"/list/RRP), require a currency indicator in the text, take the first remaining in document order. | Yes — diagnosed on a saved IKEA page. |
| 3 | Candidate provenance retained: channel, raw text, DOM path or JSON pointer, normalized `Money`, parse failure, superseded flag, and the selection reason. | No — required by this iteration's brief. |
| 4 | `PARSE_FAILURE`, `ABSENT` and `MULTIPLE_DISTINCT` are distinct channel statuses. | No — required by the brief. |
| 5 | Collection: per-domain pacing raised 1.0 s → 2.0 s, `Retry-After` honoured, exponential backoff, a growing per-domain penalty, bounded retries, and a domain marked **unavailable** rather than circumvented. | Yes — 42% of pilot responses were HTTP 429. |
| 6 | Gzipped sitemaps decompressed. | Yes — found during frame reconnaissance. |
| 7 | Channel comparison requires matching currency and single-valued channels; currency mismatch is `AMBIGUOUS_CURRENCY`, multiple offers is `AMBIGUOUS_MULTIPLE_OFFERS`. This was already declared in protocol sections 3 and 13 but had never been implemented. | Yes — the canary showed DOM USD vs JSON-LD CAD being counted as a conflict. |
| 8 | Preflight corpus and manifest added; one synthetic fixture (`dom-unparseable`) was rewritten to carry a currency so it exercises `PARSE_FAILURE` under the corrected rule rather than `ABSENT`. | Yes — fixture design, not an E threshold. |

## Why these are instrument repair, not tuning toward E

Changes 1, 2, 6 and 7 all **reduce** measured conflicts — they remove false conflicts
that the broken instrument would have produced (European decimals, dimension strings,
cross-currency offers). None of them make a genuine disagreement harder to see: the
preflight corpus contains `genuine-conflict`, and the suite fails if that page is not
reported as a conflict. No threshold in Arm E was touched.

## Known frame bias, declared

Domains that expose a product sitemap to a non-Google agent are a minority and skew
toward sites with weaker bot protection. Any future sample describes that subset, not
e-commerce in general.
