# `probe` Retest — Results

One NARROW-AND-RETEST iteration, run under `PROBE-RETEST-PROTOCOL.md`. The previous run
stands unchanged in `DIAGNOSTIC-PROTOTYPE-RESULTS.md` and is not reinterpreted here.

---

## 1. Repairs Made

Three, each traceable to a defect measured in the previous run.

**A — rendering failure became evidence.** `probe` no longer requires `networkidle`. It
waits a bounded 5 s and then reads the page as it stands, reporting one of `OK`,
`PARTIAL_RENDER`, `RENDERING_TIMEOUT` or `RENDERING_FAILED`. Raw evidence is always kept.
No retry machinery was added.

**B — HTML entities decoded at the probe boundary**, in `probe/correlate._parse`, not in
the frozen `realworld/money.py`. `&#8377;4400` parsed as the amount **8377** — the
entity's own digits — and garbled an entire report.

**C — one conservative fallback for unlabelled prices.** It runs only when no element is
marked as a price. The candidate must be an element's own short text that is essentially
just the amount: at most **8 characters** may surround the currency-and-amount token.
No site-specific selectors, no special cases, no ranking model.

**Correction to the previous report, disclosed here rather than by editing history.**
`DIAGNOSTIC-PROTOTYPE-RESULTS.md` §13 recorded ssl.com as a `probe` recall miss. Running
the reproduction before touching the extractor showed **my own baseline was wrong**:
ssl.com's `$1.75` is *"requiring full EV vetting and $1.75M warranty"* — a warranty
figure — and the other two amounts are "From $20,000/yr" in prose on a category page.
`probe` reporting no usable price there was **more correct than my manual pass**. Only
one of the two recorded misses (Notion) was real. The historical file is left as written.

## 2. Approximate LOC Changed

```
probe/observe.py      ~+45   rendering status, bounded settle, error capture
probe/correlate.py    ~+55   entity decoding, unlabelled-price fallback
probe/report.py        ~+8   RENDERING section
fixtures/probe/server  ~+20  four fixtures (never-idle, unlabelled ×2, prose)
probe/select_pdp.py    138   new frame selector
tests                 ~+95   nine regression tests
```

## 3. Regression Tests

Nine added; none weakened.

```
page that never goes idle          → PARTIAL_RENDER, report produced, raw evidence intact
navigation failure (dead port)     → RENDERING_FAILED with detail, no exception
render failure                     → report still contains the raw price
&#8377;4400                        → 4400 INR
unlabelled currency text           → discovered, marked "(unlabelled)"
two unlabelled amounts             → both reported, recommendation AMBIGUOUS
currency amount inside prose       → not treated as a price   (the ssl.com lesson)
preflight corpus via _from_dom     → all 10 priced fixtures still answered by the
                                     declared labelled rule; fallback never reached
```

**Noise check:** the fallback fires on **zero** preflight fixtures. The
`neighbouring-product` and `dimension-like-number` protections are untouched.

**Quality gate — actual output.**

```
before:  164 passed · ruff format clean · ruff check clean · mypy clean (39 files)
after:   173 passed · ruff format clean · ruff check clean · mypy clean (40 files)
```

## 4. New Sampling Protocol

`PROBE-RETEST-PROTOCOL.md` §2, frozen before any draw. Tranco `K9L5W`, top 10,000, seed
`20260819`, one target per domain. Eligibility: robots permits → homepage 200 → **≥5
product-detail paths with a trailing segment** → first such link → **price concept present
on the rendered page**. The price test was deliberately run after rendering so
client-rendered prices were not silently excluded.

**324 draws produced 10 targets.** Dominant rejection was `NOT_A_STOREFRONT`.

## 5. Ten Targets

```
 4840  espressif.com       /en/products/socs
 3412  postman.com         /product/integrations/
  936  docker.io           /products/docker-sandboxes/
 2352  grafana.com         /products/cloud/ai-assistant
 2405  notion.site         /product/ai
 6159  tomtom.com          /products/orbis-maps-for-automated-driving/
 2037  segment.com         (twilio.com)/products/conversational-ai
 1552  therapservices.net  /products/turnkey-solution-for-state-and-local-government/
  607  amazon.fr           /SPARCO-.../dp/B017JXGJM8/
 7151  webpt.com           /products/rcm-service
```

**The frame failed its declared subject, and this constrains every conclusion below.**
Only **1 of 10** (`amazon.fr`) is a genuine single-product commerce PDP. **5 of 10** carry
no price at all. The trailing-segment rule was meant to separate PDPs from `/products/`
indexes, but SaaS sites use `/products/<product-name>/`, which satisfies it, and the
rendered price-concept test passes on pricing widgets and footers. Under the frozen rules
this was not corrected mid-run, and no third iteration is being requested.

## 6. Reliability Results

**Zero crashes on 10 of 10 targets.** Previous run: 3 crashes.

`PARTIAL_RENDER` fired on **4 targets** — postman, grafana, notion, therapservices. Each
is a page that never reaches network idle, i.e. **each would have been a crash under the
old code**. The repair is directly responsible for 4 of the 10 reports existing at all.

**Kill criterion 1 (reliability): DOES NOT FIRE.**

## 7. Field Recall

No target where the agent found a price straightforwardly and `probe` reported nothing.
On all five price-free pages (postman, tomtom, twilio, therapservices, webpt) both agreed
there is no price; on webpt the agent saw `$5` inside marketing prose and rejected it, and
`probe` did too.

The previous run's one real recall miss — **notion.com, the same page** — is now
recovered: `probe` found `$0` and `$20` via the unlabelled fallback and reported both.

**Kill criterion 2 (field recall): DOES NOT FIRE.**

## 8. Per-Target Evidence

| # | Target | `probe` evidence |
|---|---|---|
| 1 | espressif | `3.8 USD` ← `ul.purchase-table>li.purchase-item>div.purchase-price-tip`; several distinct; rendering unchanged |
| 2 | postman | no value in any channel; PARTIAL_RENDER |
| 3 | docker | `0 USD` ← `div.container>div.personal-plan>div.price`; several distinct; rendering unchanged |
| 4 | grafana | `$0/$20/$2` **rendered only**, unlabelled spans; raw carries nothing |
| 5 | notion | `$0/$20` **rendered only**, unlabelled spans; raw carries nothing |
| 6 | tomtom | no value in any channel |
| 7 | twilio | no value in any channel |
| 8 | therapservices | no value in any channel; PARTIAL_RENDER |
| 9 | amazon.fr | `41.79 EUR` ← `div.celwidget>div>div.celwidget`, present in raw **and** rendered; several distinct |
| 10 | webpt | no value in any channel |

**No JSON endpoint carrying the field was found on any of the ten.** The previous run
found one (123rf's pricing API). Across these ten, five-channel correlation reduced in
practice to raw-DOM versus rendered-DOM.

## 9. Agent-Manual Findings

Recorded in `scratchpad/rt-manual-conclusions.md` **before any `probe` run**: prices
visible in raw and unchanged on espressif, docker, amazon.fr; rendering adds pricing on
grafana and notion; no price on postman, tomtom, twilio, therapservices, webpt.

Noted by the agent and **not** by `probe`: the baseline's own Chromium fetch of amazon.fr
returned a **3,538-byte bot-block page**, while `probe`'s render succeeded. `probe` has no
concept of "this render was blocked" — here it did not matter, but it is a real blind spot.

## 10. `probe` Findings

| # | `probe` | Agent | |
|---|---|---|---|
| 1 | HTTP MAY BE SUFFICIENT | HTTP sufficient, multi-product | ✓ |
| 2 | RESULT AMBIGUOUS | no price | ✓ |
| 3 | HTTP MAY BE SUFFICIENT | HTTP sufficient, tiers | ✓ |
| 4 | BROWSER RENDERING APPEARS NECESSARY | rendering adds price | ✓ |
| 5 | BROWSER RENDERING APPEARS NECESSARY | rendering adds price | ✓ |
| 6 | RESULT AMBIGUOUS | no price | ✓ |
| 7 | RESULT AMBIGUOUS | no price | ✓ |
| 8 | RESULT AMBIGUOUS | no price | ✓ |
| 9 | HTTP MAY BE SUFFICIENT | price in raw | ✓ |
| 10 | RESULT AMBIGUOUS | no price | ✓ |

**10 of 10 agreement** (previous run: 2 of 10). Tempered by the fact that **4 of those 10
are agreement that no price exists**, which is a low bar the agent cleared just as easily.

## 11. Time Comparison

Wall-clock. **Human DevTools remains UNMEASURED**; no human-time claim is made.

```
                 agent-manual   probe
total (10)          113.8s      65.0s
median               7.6s        6.2s
worst               33.3s       10.0s
```

`probe` was **1.8× faster in total** and far more consistent — worst case 10.0 s against
33.3 s. Previous run it was 2.4× *slower*. It also required no analysis step: the agent
baseline needed custom extraction scripts to reach the same conclusions.

## 12. Useful Evidence Unique to `probe`

Counted against `PROBE-RETEST-PROTOCOL.md` §4.4. **Exactly 5 of 10** — the threshold.

- **espressif, docker, amazon.fr** — exact field provenance (selector path) plus explicit
  *"rendering did not change it"*, a negative result the agent did not establish.
- **grafana, notion** — a meaningful raw-versus-rendered change: the value exists only
  after rendering, with the unlabelled spans that carry it.

Zero targets contributed a correlated JSON endpoint or a representation disagreement.

**Kill criterion 4 (usefulness): DOES NOT FIRE**, but only just — at 5, where 4 would have
killed it.

## 13. Evidence `probe` Missed

1. **Bot-blocked rendering is invisible to it** (§9). A challenge page that returns HTTP
   200 would be read as a legitimate render.
2. **It cannot say which of several prices is *the* price.** On espressif, docker and
   amazon.fr it flagged `several distinct prices` and picked the first in document order.
   Honest, but the developer still has to choose.
3. **A feature flag matched the price key** on amazon.fr —
   `script[218]/btf-sub-nav-desktop-price-and-atc-enabled` with value `'False'`. Correctly
   marked unparsed rather than reported as a value, but it is noise in the report.

## 14. Misleading Recommendations

**Zero.** `probe` recommended a cheaper path on three targets (espressif, docker,
amazon.fr) and all three genuinely carry the field in the raw body.

**Kill criterion 3: DOES NOT FIRE.** Across two runs and twenty targets, `probe` has now
produced **zero** misleading recommendations. The advisory vocabulary and the parser's
refusal to guess are holding.

## 15. Kill-Criteria Evaluation

Evaluated exactly as predeclared. Not altered after results.

| | Criterion | Result |
|---|---|---|
| 1 | Reliability — any crash | **DOES NOT FIRE** — 0 crashes, 4 graceful `PARTIAL_RENDER` |
| 2 | Field recall — ≥2 misses | **DOES NOT FIRE** — 0 misses |
| 3 | Misleading advice — ≥2 | **DOES NOT FIRE** — 0 |
| 4 | Usefulness — <5/10 useful | **DOES NOT FIRE** — exactly 5, at the threshold |
| 5 | Agent clearly faster/more complete | **DOES NOT FIRE** — `probe` was 1.8× faster and matched 10/10 |

**No kill criterion fires.**

## 16. Standalone CLI Assessment

Weak, and weaker than the criteria alone suggest.

The five-value vocabulary collapsed to three outcomes, and **four of ten runs said
"AMBIGUOUS — nothing found"**, which is not advice. On the three HTTP-sufficient targets
the recommendation was correct but incomplete: the page has several prices and the CLI
cannot say which one the developer wants. The recommendation layer added little on top of
the evidence, and the evidence is what did the work.

## 17. Evidence-Engine Assessment

**Strong, and clearly the better half of the tool.** Measured separately per §5 of the
protocol:

- deterministic, reproducible acquisition across five channels;
- exact provenance for every value — selector path or JSON pointer;
- graceful, *named* degradation on 4 of 10 real pages;
- locale-correct parsing that refused to guess and produced zero false price claims;
- faster and more consistent than an agent doing the same work by hand;
- ambiguity preserved rather than resolved — several values reported as several values.

Every one of those is a property of the acquisition layer, not of the recommendation.

## 18. MCP / Agent-Layer Assessment

The results point this way. The agent had the reasoning `probe` lacks — it distinguished a
warranty figure from a price, recognised a bot-block page, and knew a `$5` in marketing
prose was not a price. `probe` had the determinism and provenance the agent lacked, and
was faster at acquisition.

The natural division is therefore **`probe` acquires and correlates; an agent
interprets** — which is an MCP/tool primitive, not a CLI competing with the agent. Not
implemented, as instructed; recorded as the direction the evidence supports.

## 19. Novelty Assessment

Unchanged and not broadened. Never claimed: browser automation, endpoint discovery,
structured-data inspection, raw-versus-rendered comparison. The surviving primitive
remains **deterministic field-level value correlation with provenance across
representation channels** — and this run supports it only for **`price`**, only on the
population actually drawn, which was mostly SaaS product pages rather than the commerce
PDPs the frame was written to select (§5).

## 20. Final Verdict

The repairs did what they were meant to do: crashes went 3 → 0, agreement with the agent
went 2/10 → 10/10, and `probe` went from 2.4× slower to 1.8× faster. No predeclared kill
criterion fires. Zero misleading recommendations across twenty targets and two runs.

But the case for a standalone CLI is not what improved. Four of ten runs produced no
advice, the usefulness criterion passed at exactly its threshold, no JSON endpoint was
correlated on any target, and the recommendation layer added little over the evidence
beneath it. What improved is **acquisition**: deterministic, provenance-carrying,
gracefully degrading, fast. And the agent beat `probe` at every judgement that required
knowing what a price *means*.

Two limits bound this result and must travel with it: the frame delivered **one** genuine
commerce PDP out of ten, so the declared population was not tested; and the whole result
covers one field.

**BUILD OSS MVP — EVIDENCE ENGINE + MCP FIRST**

The evidence engine earned this; the CLI did not. The MVP should expose deterministic
field-level evidence with provenance to an agent, and must not lead with the
recommendation vocabulary. Before any claim beyond `price` on SaaS-and-one-PDP pages, the
frame must be fixed and the population actually tested.
