# Diagnostic Prototype — Results

Result of the `probe` experiment defined in `PROBE-PROTOCOL.md`. Measurements were taken
in this session. Nothing here is estimated.

---

## 1. Novelty Gate Verdict

**PROCEED — DIFFERENTIATION NARROWED** (`DIAGNOSTIC-NOVELTY-GATE.md` §1).

Closest prior art on two axes: **`browser-recon`** (closest in form — URL in, "verified
scraping plan" out, but on the *transport* axis: anti-bot vendor, headers, cookies, proxy
tier; server-side, proprietary, API-key gated, human-paced) and **`chrome-devtools-mcp`**
(closest in capability — an LLM agent holding it can run the whole DevTools workflow; a
control surface, not a reproducible report). Also recorded: `yfe404/web-scraper`, a Claude
skill implementing the same "All data in HTML? → skip the browser" gate by prompting.

## 2. Exact Surviving Differentiation

> A local, deterministic tool that correlates a requested field's value across raw HTML,
> structured metadata, embedded state, rendered DOM and network JSON, preserving
> provenance and reporting where representations disagree.

Never claimed: structured-data inspection, endpoint/API discovery, raw-vs-rendered
comparison, browser automation, scrape-target diagnosis in general.

## 3. Target Selection Procedure

Frozen before any draw (`PROBE-PROTOCOL.md` §6, Addendum B). Tranco list `K9L5W`
(2026-08-17), top 10,000 ranks, seeded shuffle `seed = 20260818`. A domain qualifies when
robots permits and its homepage returns 200; the target is the first same-host link in
homepage document order whose path matches the product-path pattern frozen in
`PILOT-PROTOCOL.md` Addendum A1. JSON-LD, endpoints, client-rendering, disagreement and
extraction success were never consulted.

## 4. Original Invalid Draw

Preserved in `results/probe/targets.json`. The first draw was subject-blind and returned
two login forms, a signup form, an org chart, an editor and a video page — pages with no
price. §2 froze a price-only field while §6 froze a subject-blind frame; the two do not
compose. Halted **before any target was probed**; recorded in `PROBE-PROTOCOL.md` §12.

## 5. Corrected Commerce Draw

Addendum B, declared before the redraw. Same seed, order, field, tool and rules; only the
subject axis changed. **293 draws produced 10 qualifying targets.** Dispositions:

```
101 NO_PRODUCT_LINK   54 ROBOTS_UNREACHABLE   20 ROBOTS_TIMEOUT   11 HTTP_403
 11 DISALLOWED        10 SELECTED              3 HTTP_404          1 UNREACHABLE
  1 ROBOTS_OVERSIZED
```

The first attempt at this redraw stalled for 106 minutes on draw #34 (`sahibinden.com`)
because `RobotFileParser.read()` calls `urlopen()` with no timeout. That defect, its
repair, and the audit are documented in `PROBE-PROTOCOL.md` §14. On the repaired run
`sahibinden.com` returned `DISALLOWED` and the draw continued. **20 `ROBOTS_TIMEOUT`
dispositions occurred across the completed draw** — under the old code any one of them
could have stalled it indefinitely.

**Live-web variability, recorded as a limitation, not corrected:** `fonts.net` was
`ROBOTS_DISALLOWED` in the first run and `ROBOTS_TIMEOUT` in the second. Robots
dispositions for flaky hosts are not stable across runs. The progress log now captures
this rather than hiding it.

## 6. Ten Targets

```
 4622  123rf.com            https://www.123rf.com/products/
 2591  crowdstrike.com      https://www.crowdstrike.com/en-us/products/
 6003  workday.com          https://www.workday.com/en-us/products/human-capital-management/overview.html
 4000  lazada.sg            https://www.lazada.sg/products/pdp-i111650098-s23209659764.html
 9152  amazonses.com        https://aws.amazon.com/products/developer-tools/agent-toolkit-for-aws/
 2776  thomsonreuters.com   https://www.thomsonreuters.com/en/products/proview
 8848  mova-tech.com        https://www.mova.tech/products/mova-1000-robot-lawn-mower
 1811  notion.com           https://www.notion.com/product/ai
  750  sophos.com           https://www.sophos.com/en-gb/products/contact-request
 2934  ssl.com              https://www.ssl.com/products/
```

**Frame observation, stated because it constrains everything below:** the product-path
pattern was designed for e-commerce sitemaps. Applied to a general top-10k frame it
mostly matches **B2B "our products" marketing pages**, not priced product detail pages.
Exactly **two** targets are conventional priced PDPs (`lazada.sg`, `mova-tech.com`); one
is a contact form; three carry no price at all. This was not corrected — the draw is
frozen — but it means the run tests the diagnostic on a population where the requested
field is frequently absent by nature.

## 7. Per-Target Unaided Findings

Recorded in `scratchpad/manual-conclusions.md` **before any `probe` run**.

| # | Target | Unaided conclusion |
|---|---|---|
| 1 | 123rf.com | Prices in raw (₹1430/2190/501, $25,000/$100,000); rendering adds more. Multi-plan listing, no single price. → AMBIGUOUS |
| 2 | crowdstrike.com | Prices in raw ($7.99–$184.99); cart spans empty but tile prices server-rendered. → HTTP SUFFICIENT |
| 3 | workday.com | No price anywhere. → NO PRICE EXISTS |
| 4 | lazada.sg | $38.00 in raw; JSON-LD Product present. → HTTP SUFFICIENT |
| 5 | aws.amazon.com | No price anywhere; 4 JSON-LD blocks, none priced. → NO PRICE EXISTS |
| 6 | thomsonreuters.com | No price anywhere. → NO PRICE EXISTS |
| 7 | mova-tech.com | JSON-LD price `0.00`, displayed `$0.00`, raw and rendered. → price present but ZERO |
| 8 | notion.com | Raw has $10; rendered has $0/$10/$20. → RENDERING ADDS PRICE |
| 9 | sophos.com | Raw HTTP fetch timed out (`httpx.ReadTimeout`). → UNREACHABLE |
| 10 | ssl.com | $1.75/$12,500/$20,000 in both raw and rendered, unchanged. → HTTP SUFFICIENT |

## 8. Per-Target `probe` Findings

| # | Target | Runtime | `probe` result | vs unaided |
|---|---|---|---|---|
| 1 | 123rf.com | 7.5s | RESULT AMBIGUOUS | agrees, but see §14 — report garbled |
| 2 | crowdstrike.com | 7.7s | HTTP MAY BE SUFFICIENT | **AGREES** |
| 3 | workday.com | 32.0s | **CRASH** — `TimeoutError` on `networkidle` | no output |
| 4 | lazada.sg | 34.8s | **CRASH** — `TimeoutError` on `networkidle` | no output |
| 5 | aws.amazon.com | **270.8s** | RESULT AMBIGUOUS | agrees (no price exists) |
| 6 | thomsonreuters.com | 0.2s | refused: `ROBOTS_UNREACHABLE` | correct refusal |
| 7 | mova-tech.com | 28.8s | STRUCTURED METADATA MAY BE SUFFICIENT | **AGREES** |
| 8 | notion.com | 9.6s | RESULT AMBIGUOUS (no value found) | **MISS** — price exists |
| 9 | sophos.com | 1.1s | **CRASH** — `ERR_HTTP2_PROTOCOL_ERROR` | no output |
| 10 | ssl.com | 15.6s | RESULT AMBIGUOUS (no value found) | **MISS** — price exists |

**Correct and useful: 2 of 10** (t02, t07). Plus one correct refusal (t06) and two correct
"no price" agreements (t05, and t01 by conclusion if not by presentation).

## 9. Agent + DevTools Baseline

**AGENT BASELINE: QUALITATIVE / NOT MEASURED.**

`chrome-devtools-mcp` was not installed or wired into this session, so it was not
executed. No timing is claimed for it. Qualitatively, on these ten targets an agent with
`list_network_requests` and DOM access would have reached the unaided conclusions —
because *this session's unaided baseline is itself an LLM agent* reading raw HTML and an
unfiltered network log, which is the same information by a different interface.

## 10. Time Comparison

Wall-clock only. **The human-DevTools component is UNMEASURED and no human-time claim is
made.**

```
                     unaided (agent)   probe
total across 10        172.8s          408.1s
median                  16.4s           12.6s
worst                   34.1s          270.8s   (aws.amazon.com)
```

`probe` was **2.4× slower in total**, dominated by one 270-second target. Median runtimes
are comparable. The unaided baseline additionally required two batched analysis steps
across all ten targets; `probe` requires none when it produces a report — but on 6 of 10
targets it did not produce a usable one, so the raw dump had to be read anyway.

**`probe` did not materially outperform the measured agent-manual baseline.** Per the
frozen instruction, no argument is offered that a human would have been slower.

## 11. Field-Level Correlation Results

The differentiator worked on the targets where the instrument worked at all.

- **t07 mova-tech.com** — traced the value to `script[1]/offers/0/price` and reported
  `0.0 USD` with that exact JSON pointer. The unaided baseline found the value but not the
  pointer.
- **t02 crowdstrike.com** — traced `$7.99` to
  `div.cmp-product-card-v2>…>div.cmp-product-card-v2__price-container`, confirmed
  RAW_DOM and RENDERED_DOM carry the same value, and flagged `several distinct prices on
  the page`. The unaided baseline found the value but not the selector, and did not
  establish that rendering left it unchanged.
- **t01 123rf.com** — **found the JSON endpoint the unaided baseline missed entirely**:
  `GET https://www.123rf.com/apicore/products/subs?country=IN&packageType=14`, with
  per-field JSON pointers into `/data/attributes/subs/0/price/…`. This is the single
  clearest instance of the tool surfacing something the investigation had not.

Cross-channel correlation therefore does produce evidence the unaided pass missed — on
3 of 10 targets — but only one of those three reports was legible enough to act on.

## 12. Useful Evidence Surfaced Automatically

1. The 123rf pricing API endpoint with exact JSON pointers (t01) — not found unaided.
2. Exact provenance for every reported value: DOM selector path or JSON pointer (t01, t02, t07).
3. Explicit "rendering did not change it" confirmation (t02, t07) — a negative result the
   unaided pass did not establish.
4. `several distinct prices on the page` as an honest ambiguity flag rather than a silent
   pick (t01, t02).

## 13. Important Evidence Missed

1. **t08 notion.com** — `$10` in raw and `$0/$10/$20` after rendering. `probe` found
   nothing in any channel. The frozen DOM rule requires a `price`-labelled `class`/`id`/
   `data-testid`; Notion's markup has none. The unaided baseline found it with a currency-
   symbol scan.
2. **t10 ssl.com** — `$1.75/$12,500/$20,000` present in both raw and rendered. Same cause,
   same miss.
3. **t03, t04, t09** — no evidence at all, because the tool crashed (§14).

The false-negative mode is structural: prices not carried in price-labelled elements are
invisible to the frozen extractor. Two of ten targets, and both were pages where the
unaided answer was easy.

## 14. Misleading Recommendations

**Zero.** `probe` never recommended a cheaper path that does not carry the field. Its
failure mode is silence (`RESULT AMBIGUOUS`) or a crash, not false confidence. Kill
criterion 2 does not fire, and this is a genuine point in the design's favour: the
advisory vocabulary and the refusal-to-guess parser held under real input.

**Two implementation defects were found and are documented, not repaired**, because the
standing instruction for this phase is to measure and report:

**(a) Unhandled rendering failure — 3 of 10 targets.** `probe` waits for `networkidle`
and does not catch Playwright's `TimeoutError`, so a page with continuous background
activity produces a traceback instead of a report (t03, t04). A transport-level
navigation failure does the same (t09, `ERR_HTTP2_PROTOCOL_ERROR`). The baseline
apparatus caught the identical condition and degraded gracefully; `probe` does not. **A
diagnostic that dies on 30% of real pages is not usable**, and this is product evidence,
not merely instrument noise.

**(b) HTML entities are parsed as amounts.** Verified directly:

```
parse_money('&#8377;4400')  ->  8377 ?          # the entity's digits become the amount
parse_money('₹4400')        ->  4400 INR        # correct
```

Embedded-JSON values carrying entity-escaped currency symbols are therefore reported as
nonsense. This produced t01's findings line — *"Channels report different currencies
(1760, 2200, 3520, 3960, 4400, 4749, 7690, INR)"* — in which amounts are printed as
currencies. The fix belongs in `probe` (decode entities before parsing), not in the paused
`realworld/money.py`.

## 15. Determinism / Reproducibility

The fixture suite asserts byte-stable reports, and that test passes. On live targets
determinism is bounded by the sites themselves — content, A/B assignment and network
timing vary between runs — so the *report generation* is deterministic while the
*observation* is not. This is a real limit on the "diffable, CI-usable" claim: `probe`
guarantees the same bytes produce the same report, not that the same URL produces the
same bytes.

## 16. Kill-Criteria Evaluation

Evaluated exactly as frozen in `PROBE-PROTOCOL.md` §9. Not reinterpreted.

**1. No meaningful time saving — DOES NOT FIRE, on an empty population.** The criterion
counts only targets where unaided diagnosis took more than 5 minutes. No target did: the
agent-manual baseline resolved each in seconds of wall-clock. The criterion cannot fire
because its population is empty, **not because `probe` saved time — it did not** (§10).
The human-DevTools component of this criterion is **UNMEASURED**.

**2. Misleading advice — DOES NOT FIRE.** Zero misleading recommendations (§14).

**3. Mostly noise — FIRES.** The criterion requires 5 or more targets where reaching the
conclusion needs more than ~60 lines of report or the raw dump anyway. Six qualify:
t01 (report exceeds 60 lines and its findings are garbled), t03, t04, t09 (no report at
all — dump mandatory), t08 and t10 (report says nothing found while a price exists, so
the dump was required to discover the tool was wrong).

**4. Existing tool equivalent — DOES NOT FIRE.** Nothing in implementation or testing
showed an existing tool providing this experience. `browser-recon` and
`chrome-devtools-mcp` remain adjacent, not equivalent.

**One kill criterion fires.**

## 17. Competitive Assessment

Against `browser-recon`: still a different axis, and `probe`'s local-and-deterministic
properties are real. But `browser-recon` presumably returns a usable report on pages where
`probe` crashes, because handling hostile, slow, flaky sites *is* its subject matter.

Against `chrome-devtools-mcp` + an agent: on these ten targets the agent workflow produced
**more correct conclusions than `probe` did** — it found the prices on t08 and t10 that
`probe` missed, and it degraded gracefully on t03/t04/t09 where `probe` crashed. `probe`
beat it on exactly one dimension: it found the 123rf pricing endpoint, which the agent
pass did not.

## 18. Value Beyond DevTools

Demonstrated on 3 of 10 targets: exact provenance, an automatically discovered endpoint,
and explicit "rendering changed nothing" confirmation. Not demonstrated on the other
seven.

## 19. Value Beyond Agent + DevTools

**Not demonstrated by this run.** The deterministic, provenance-carrying report is a real
property, and on t01 it surfaced an endpoint the agent pass missed. But an agent with
browser tools produced more correct answers overall on the same ten targets. Per the
frozen instruction: *the deterministic/reproducible advantage may not be sufficient for
standalone adoption* — on this evidence it is not.

## 20. Scope Limitation — Price / Commerce Only

This experiment validates nothing beyond **price diagnosis on pages reached by a
product-path filter**. It does not support any claim about arbitrary-field diagnosis. And
even within that scope, §6 records that the filter mostly yields B2B marketing pages
rather than priced PDPs, so the applicable population is narrower still.

## 21. What Existing Validation Infrastructure Contributed

- The **currency-aware money parser** with its refusal to guess produced zero misleading
  price claims on live pages (§14) — and its one real gap, HTML entities, was caught by
  this run.
- The **channel-extraction-with-provenance** work is what makes §11 possible at all; it
  was reused unchanged.
- The **preflight/fixture discipline** produced 13 behaviour tests that all passed while
  the tool nonetheless failed on 30% of real pages — a direct, useful reminder that green
  fixtures are not evidence of field readiness.
- The **mid-run defect policy** is what caused the subject/field mismatch to be caught
  before any target was probed, rather than after.

## 22. Final Verdict

Kill criterion 3 fires. `probe` did not outperform the measured agent-manual baseline, it
missed prices the baseline found on 2 targets, and it crashed on 3. Against that, it
produced zero misleading recommendations, and on 3 targets it surfaced provenance and one
JSON endpoint the baseline did not.

Four of the six targets that triggered the noise criterion did so because of two specific,
identified implementation defects — unhandled rendering failure and entity-mangled money
parsing — not because cross-representation correlation is uninformative. The hypothesis
was therefore not cleanly tested. But the defects are in the product itself, so this is
not the "invalid instrument" situation that would justify discarding the run: a diagnostic
that crashes on 30% of real pages has told us something true about its readiness.

The evidence does not support building an MVP, and does not yet justify abandoning the
one capability that did work.

**NARROW AND RETEST**

This is not an endorsement. It means: repair the two defects with regression tests, retest
on a frame that actually contains single-priced product pages, and **if the DOM
false-negative rate persists, kill it** — a diagnostic that misses the field on pages
where a currency-symbol scan finds it in seconds has no case. The `probe` prototype is
unfit for use in its current state and no claim about it should be made outside this file.
