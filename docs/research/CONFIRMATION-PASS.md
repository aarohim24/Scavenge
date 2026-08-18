# Confirmation Pass — Pinned Source Verification

Date checked: 2026-08-17. No implementation code written. `CLAUDE.md`, `AGENT.md`,
`SKILLS.md`, `RESEARCH-GATE.md` unmodified.

---

## 1. Pinned Sources

**Crawlee for Python**

| | |
|---|---|
| Version | **1.9.2** (latest stable) |
| Git tag | `v1.9.2` |
| Commit SHA | `890148d6ce55cdd6ac0e8cac87e2879eaef4910b` |
| Tag date | 2026-08-17T12:28:54+02:00 |
| Verified `pyproject.toml` | `version = "1.9.2"` |
| Method | `git clone` + `git checkout v1.9.2`, files read locally |

**Process note worth recording.** My first attempt at pinning was wrong.
`pip download crawlee` on this machine resolved **0.6.12**, because the local
interpreter is Python 3.9.6 and 0.6.12 is the last release supporting it. Had I
trusted that, the entire pass would have been run against a release from
2025-07-30, one major version and ~20 minor versions stale — and it lacks
predictor persistence entirely, which would have made Claim E look FALSE. The
`git ls-remote --tags` listing showed `v1.9.2` as current. **Any future
measurement work must not use this machine's default Python 3.9 environment.**

Also inspected: `apify/crawlee` (JS) `master` for the reference implementation,
Crawlee issue tracker via `gh`, and the wrapper-verification literature.

All line numbers below refer to the pinned SHA.

---

## 2. Claim-by-Claim Verification

### Claim A — escalation can depend on the extraction result via `result_checker`
**CONFIRMED**, with an important scope limit.

* `_adaptive_playwright_crawler.py`, `AdaptivePlaywrightCrawler._run_request_handler`, [L394–L405](https://github.com/apify/crawlee-python/blob/890148d6ce55cdd6ac0e8cac87e2879eaef4910b/src/crawlee/crawlers/_adaptive_playwright/_adaptive_playwright_crawler.py#L394-L405)

```python
static_run = await self._crawl_one(rendering_type='static', context=context)
if static_run.result and self.result_checker(static_run.result):
    self._context_result_map[context] = static_run.result
    return
```

Proves the cheap path commits only if the checker accepts the extraction result.

**Scope limit, verified in code:** this block is reachable only when
`should_detect_rendering_type` is false **and** the prediction is `'static'`
([L386–L394](https://github.com/apify/crawlee-python/blob/890148d6ce55cdd6ac0e8cac87e2879eaef4910b/src/crawlee/crawlers/_adaptive_playwright/_adaptive_playwright_crawler.py#L386-L394)).
The checker is **never applied to the browser result** and never consulted when
the prediction is `'client only'`. It is a static-path gate, not a general
extraction-validity gate.

### Claim B — a failed static `result_checker` continues with browser rendering
**CONFIRMED, and covered by an upstream test.**

Control flow: the `return` at L397 is the only early exit; failing the checker
falls through to L406 `'Running browser request handler'` and L422
`pw_run = await self._crawl_one('client only', ...)`. The failure is counted as a
misprediction at L404.

Upstream test, `tests/unit/crawlers/_adaptive_playwright/test_adaptive_playwright_crawler.py::test_adaptive_crawling_statistics`
— constructs the crawler with `result_checker=lambda result: False` and a
no-detection static predictor, then asserts
`http_only_request_handler_runs == 1`, `browser_request_handler_runs == 1`,
`rendering_type_mispredictions == 1`, and `requests_finished == 1`. This is
Crawlee's own regression test for the exact behavior we assumed.

### Claim C — Crawlee periodically runs both modes and compares extraction results
**CONFIRMED, with two corrections to `RESEARCH-GATE.md`.**

* [L383–L384](https://github.com/apify/crawlee-python/blob/890148d6ce55cdd6ac0e8cac87e2879eaef4910b/src/crawlee/crawlers/_adaptive_playwright/_adaptive_playwright_crawler.py#L383-L384): `should_detect_rendering_type = random() < rendering_type_prediction.detection_probability_recommendation` — per-request Bernoulli sample.
* [L422–L438](https://github.com/apify/crawlee-python/blob/890148d6ce55cdd6ac0e8cac87e2879eaef4910b/src/crawlee/crawlers/_adaptive_playwright/_adaptive_playwright_crawler.py#L422-L438): browser runs, then `static_run = await self._crawl_one('static', ..., state=old_state_copy)`, then `result_comparator(static_run.result, pw_run.result)` → `'static'` or `'client only'` → `store_result`.

**Correction 1 — order and cost.** During detection the **browser runs first and
unconditionally**, and the returned result is always `pw_run.result` (L440). So a
detection request costs browser + HTTP, i.e. *more* than always-browser. My
earlier report implied HTTP-then-compare. Learning is strictly more expensive than
the browser baseline for sampled requests.

**Correction 2 — comparison is conditional on how you configure it.** See §4.

### Claim D — the predictor predicts from URL-derived information, not from evidence in the cheap document
**CONFIRMED.**

`_rendering_type_predictor.py`, `DefaultRenderingTypePredictor`:
* `predict()` [L~185–L205]: takes `request` only; features from `get_url_components(request.url)` and `request.label`. No document is in scope.
* `_calculate_feature_vector` → `(mean_similarity_to_static_urls, mean_similarity_to_client_only_urls)` — a 2-float vector.
* `calculate_url_similarity`: returns 0 for different hosts, 1 for identical URLs, otherwise the mean over path components of `1 if jaro_winkler_metric(a, b) > 0.8 else 0`.
* `LogisticRegression(max_iter=1000)` over that 2-vector; `_retrain()` seeds with two dummy rows `[(0,1),(1,0)] → [0,1]`.
* `predict()` returns `detection_probability_recommendation = 1.0` when `abs(p0 - p1) < 0.1` (unreliable ⇒ always detect), else `detection_ratio * labels_coefficients[label]`.

The model's entire input is **string similarity of URL path components within the
same host, bucketed by request label**. The document in hand is never inspected.
This is the sharpest verified distinction available to us.

### Claim E — predictor state can persist across lifecycle/recovery
**PARTIALLY CONFIRMED — the capability exists but is OFF by default.**

`DefaultRenderingTypePredictor.__init__` [L122–L156]:
```python
def __init__(self, detection_ratio: float = 0.1, *,
             persistence_enabled: bool = False,
             persist_state_key: str = 'rendering-type-predictor-state') -> None:
```
State is a `RecoverableState[RenderingTypePredictorState]` holding the pickled
sklearn model (`sklearn_model_serializer` / `sklearn_model_validator` in
`_utils.py`) plus `labels_coefficients`; `initialize()`/`teardown()` are driven by
the predictor being registered in `_additional_context_managers`
([L222–L228](https://github.com/apify/crawlee-python/blob/890148d6ce55cdd6ac0e8cac87e2879eaef4910b/src/crawlee/crawlers/_adaptive_playwright/_adaptive_playwright_crawler.py#L222-L228)).

But `persistence_enabled=False` is the default, and the crawler constructs
`DefaultRenderingTypePredictor()` with no arguments when none is supplied
([L148](https://github.com/apify/crawlee-python/blob/890148d6ce55cdd6ac0e8cac87e2879eaef4910b/src/crawlee/crawlers/_adaptive_playwright/_adaptive_playwright_crawler.py#L148)).
**Out of the box, everything learned is discarded at the end of a run.** Our
earlier report overstated this as simply "persisted."

### Claim F — Crawlee provides no per-field evidence system and does not use evidence for sufficiency
**CONFIRMED.**

`result_checker` and `result_comparator` are typed over
`RequestHandlerRunResult` ([L125–L126](https://github.com/apify/crawlee-python/blob/890148d6ce55cdd6ac0e8cac87e2879eaef4910b/src/crawlee/crawlers/_adaptive_playwright/_adaptive_playwright_crawler.py#L125-L126)),
whose comparable surface is `push_data_calls`, `add_requests_calls`, and
`key_value_store_changes` (`_result_comparator.py` L30–L34). These are
user-authored dataset payloads. There is no `source_type`, no
`source_location`, no document hash, no candidate set, no execution-mode tag on
any value, and nothing consumes such data. Adaptive statistics are three integers
— `http_only_request_handler_runs`, `browser_request_handler_runs`,
`rendering_type_mispredictions` — with no CPU, memory, or bytes accounting.

### Claim G — the default `result_checker` provides no domain-independent correctness verification
**CONFIRMED.**

[L149](https://github.com/apify/crawlee-python/blob/890148d6ce55cdd6ac0e8cac87e2879eaef4910b/src/crawlee/crawlers/_adaptive_playwright/_adaptive_playwright_crawler.py#L149):
```python
self.result_checker = result_checker or (lambda _: True)
```

---

## 3. What Crawlee Actually Does

Steady state, per request:

1. `predict(request)` → `(rendering_type, detection_probability_recommendation)` from URL-component similarity within host, per label.
2. Sample `random() < detection_probability_recommendation`.
3. **Not sampled, predicted `'static'`** → run HTTP; commit if `result_checker` passes; else log a misprediction and run the browser.
4. **Not sampled, predicted `'client only'`** → run the browser directly. No checker, no HTTP attempt.
5. **Sampled** → run the browser (always), snapshot `use_state`, run HTTP against that snapshot, `result_comparator` → label, `store_result` → retrain. Return the **browser** result.

Cost shape: the learning mechanism is *browser-funded*. Sampled requests cost
browser + HTTP. `detection_probability_recommendation` is forced to `1.0`
whenever the logistic model's two class probabilities are within 0.1, so cold
start and ambiguous hosts dual-render on **every** request until the model
separates.

Browser reuse is real and default: the `PlaywrightCrawler`'s `_browser_pool` is
registered as a crawler-lifetime context manager (L227);
`PlaywrightBrowserPlugin` defaults to `max_open_pages_per_browser = 20`
(`src/crawlee/browsers/_playwright_browser_plugin.py:51`) and `BrowserPool`
defaults to `retire_browser_after_page_count = 100`
(`src/crawlee/browsers/_browser_pool.py:56`). The adaptive crawler also defaults
`ConcurrencySettings(desired_concurrency=1)` (L153–L154).

---

## 4. What Crawlee Does Not Do

Four verified gaps, in descending order of significance.

**(a) Supplying a `result_checker` silently replaces cross-mode comparison.**
`_result_comparator.py` [L11–L19](https://github.com/apify/crawlee-python/blob/890148d6ce55cdd6ac0e8cac87e2879eaef4910b/src/crawlee/crawlers/_adaptive_playwright/_result_comparator.py#L11-L19):

```python
def create_default_comparator(result_checker):
    if result_checker:
        # Fallback comparator if only user-specific checker is defined.
        return lambda result_1, result_2: result_checker(result_1) and result_checker(result_2)
    return push_data_only_comparator
```

Wired at L150: `self.result_comparator = result_comparator or create_default_comparator(result_checker)`.
Identical in the JS reference implementation (`resultComparator = (a, b) => this.resultChecker(a) && this.resultChecker(b)`).

Consequence: pass a checker and no comparator, and detection stops asking *"do
HTTP and browser agree?"* and starts asking *"are both individually plausible?"*
Our canonical failure case — HTTP JSON-LD `price = 2999`, rendered DOM
`price = 1999` — is then labeled **`'static'`**, because a `price is a positive
number` checker passes on both. The predictor is trained to skip the browser
precisely where the browser was necessary. **This is Crawlee's default wiring for
anyone who supplies a checker, which is exactly what a serious user does.**

**(b) Empty-extraction agreement is read as agreement.** With the default
`push_data_only_comparator`, if both runs extract nothing, `[] == []` → labeled
`'static'`. Independently reported upstream (§6).

**(c) No cost accounting.** Three counters, no CPU/RSS/bytes. Nothing in the
codebase optimizes or even measures compute per correct extraction, despite the
docstring's "performance benefit" framing (L88–L89).

**(d) No evidence model, no third tier, persistence off by default.** As per
Claims D–F.

---

## 5. Can Our Idea Be Just a `result_checker`?

**Substantially yes. This is the honest answer and it eliminates OPTION 1.**

A schema-driven sufficiency decision — required fields present, types valid,
cardinality as expected, no conflicting candidates — is expressible as a
`Callable[[RequestHandlerRunResult], bool]` closing over the schema. Provenance
can ride along inside the pushed dict (`{"price": 1999, "_src": "JSON_LD",
"_loc": "/offers/0/price"}`) and be stripped before storage. Plausibly **50–200
lines** of application code plus a shared helper module. Nothing in Crawlee's
architecture prevents it, and no fork is required.

Three real frictions, none of which justify a separate runtime:

1. **You must also pass a comparator**, or you disable comparison (§4a). Our library must ship a matched `(checker, comparator)` pair. That is a library concern, not an architecture concern.
2. **The checker can't see the browser side**, and isn't consulted on `'client only'` predictions, so it cannot catch browser-side false success or rescue pages the predictor has written off. Fixing that is a small upstream patch to `_run_request_handler`, not a new project.
3. **`RequestHandlerRunResult` carries dataset payloads, not typed evidence**, so provenance travels as convention rather than as a type. Ugly; works.

The claim that survives is therefore *not* "we need a new runtime." It is: **the
decision content is unwritten, and nobody knows whether a sophisticated checker
beats a two-line one.** Which is a measurement question, not a coding question.

---

## 6. Relevant Crawlee Issues/Discussions

* **[apify/crawlee-python#2096 — "Rendering type detection treats a failed static run as 'client only'"](https://github.com/apify/crawlee-python/issues/2096)** — OPEN, filed 2026-07-28, label `t-tooling`, no maintainer resolution. Reported against 1.8.4 at the same lines analyzed above. Two findings, both ours:
  * `static_run.exception` is never checked, so a transient static failure trains the predictor with `'client only'`; the reporter notes the label then *lowers* the re-detection probability, so "a transient failure during one detection seems like it can keep similar URLs on the browser path for a while, with nothing logged." Asymmetric with the browser side, which re-raises rather than labeling (L425–L426).
  * "with the default `push_data_only_comparator`, if both sub-crawlers succeed but the handler extracts nothing from either (both got served a challenge page), `[] == []` compares equal and the request is labeled `'static'`." Hit in production on a soft-blocked Google URL returning HTTP 200.
  This is **independent third-party evidence** that adaptive-rendering decisions are silently miscalibrated in both directions, and that it is unfixed upstream.
* [#249 — "Adaptive playwright crawler"](https://github.com/apify/crawlee-python/issues/249) — CLOSED, the original implementation issue; establishes the JS `adaptive-playwright-crawler.ts` as the reference spec.
* [#1298 — "Create optimization guide for Crawlers"](https://github.com/apify/crawlee-python/issues/1298) — OPEN; resource guidance is acknowledged as missing documentation.
* [#983 — "Proposal to Add a PolicyCrawler to Crawlee"](https://github.com/apify/crawlee-python/issues/983) — CLOSED; a rejected policy-layer proposal, useful as evidence of what the maintainers do not want in-tree.

Searches for `browser pool memory` and `playwright performance memory` in the
tracker returned nothing. **No issues found from users complaining about
unnecessary browser execution costs.** That absence is a demand signal against
us and is recorded as such.

---

## 7. Research Prior Art

**The verification half of our idea is 25-year-old research, and we must cite it.**

* **Kushmerick, "Wrapper verification," World Wide Web 3(2), 2000** ([Springer](https://link.springer.com/article/10.1023/A%3A1019229612909)), and **"Regression testing for wrapper maintenance," AAAI-99** ([PDF](https://cdn.aaai.org/AAAI/1999/AAAI99-011.pdf)). The **RAPTURE** algorithm decides whether a wrapper is still extracting correct data by comparing distributional features of extracted strings against a pre-verified baseline — nine features: digit / letter / uppercase / lowercase / punctuation / HTML density, length, word count, mean word length — thresholded into a probability that the wrapper is still correct. This is "is this extracted value trustworthy, judged without a reference run," which is our sufficiency layer's core question. RESEARCH RESULT.
* **Lerman, Minton & Knoblock, "Wrapper Maintenance: A Machine Learning Approach," JAIR 18, 2003** ([arXiv:1106.4872](https://arxiv.org/abs/1106.4872)). Verification + reinduction, evaluated on 27 wrappers over one year: **verification 0.73 precision / 0.95 recall**. RESEARCH RESULT.
* **Reported limitation, directly relevant to our risk model:** if the generic content features of a changed field resemble the pre-verified baseline, these systems cannot detect the change — and HTML density alone accounted for nearly all detections. A stale-but-well-formed `2999` is exactly the undetectable case. Independent, 20-year-old evidence that one-sided verification has a real detection ceiling.
* Schema-guided wrapper maintenance ([WIDM'03](https://ics.uci.edu/~chenli/pub/widm03.pdf)) and later work continue this line.

**What the sweep did not find:** no paper coupling extraction-verification to a
rendering/execution-mode decision; no cost-aware crawling paper optimizing
correct-extractions-per-CPU-second; no benchmark measuring extraction correctness
against compute across static and JS-heavy sites. Searches covered adaptive/
selective rendering, cost-aware crawling, rendering prediction, extraction
confidence/provenance/verification, and selective JavaScript execution; hits were
vendor blogs plus the wrapper-maintenance line above. Adjacent-but-different:
coverage-aware crawling ([arXiv:2602.24262](https://arxiv.org/html/2602.24262v3)),
which optimizes page coverage, not rendering cost.

**Effect on the thesis:** the verification technique is not novel and should be
*reused* (RAPTURE-style content features are a strong, cheap baseline our checker
should be measured against). The remaining novelty narrows to the coupling and
the measurement.

---

## 8. Correct Browser-Cost Model

`RESEARCH-GATE.md` said "the expensive thing is launching Chromium." That is
**not established**, and the pinned code shows why it is probably wrong.

Decomposition, with what the code tells us:

| Component | Amortization in Crawlee | Expected weight |
|---|---|---|
| Browser **process startup** | Amortized over ≤20 concurrent pages/browser and ≤100 pages before retirement | **per-page share is small** |
| **Context** creation | Per-page-ish in Crawlee's model | small–moderate |
| **Page** creation | Per navigation | small |
| **Navigation** + network | Per navigation, unavoidable in any mode | moderate |
| **JS execution** | Per navigation, this is what HTTP mode actually skips | **likely dominant, page-dependent** |
| **DOM/layout/paint** | Per navigation | moderate–high |
| **Retained RSS** of the warm pool | Held for the whole run regardless of per-page work | **dominant memory term** |

With `max_open_pages_per_browser=20` and `retire_browser_after_page_count=100`,
a Crawlee browser run does roughly one process launch per 20–100 navigations.
So process launches are a **diagnostic**, not a cost driver, and "Chromium
launches avoided" is close to meaningless as a headline. What HTTP mode actually
avoids is a **browser-rendered navigation** — JS execution, layout, and that
page's share of retained memory.

There is a second, opposite effect the model must include: Crawlee's *learning*
costs browser + HTTP per detection sample, and detection is forced to probability
1.0 whenever the model is unsure. So the honest comparison is not
steady-state-vs-steady-state; it must include the cold-start and
ambiguous-host regimes where Crawlee dual-renders.

**None of these weights are measured yet.** Milestone 0 of any experiment is to
measure the split — startup vs navigation vs JS vs retained RSS — on the fixture
set before any policy work. If JS execution is not the dominant term, the thesis
is dead on arrival and we will know it in a day.

---

## 9. Correct Benchmark Metrics

**Primary**
1. **CPU-seconds per correct extraction** — the cost metric.
2. **Browser-rendered navigations per 1,000 tasks** — the execution metric that actually maps to cost.
3. **False-success rate** — confidently wrong output; weighted as the most serious failure.
4. **Complete-record accuracy** — the correctness metric users care about.
5. **Memory-seconds per correct extraction** (RSS integrated over run time) — because a warm pool's cost is occupancy, not events.

**Secondary / diagnostic**
* Chromium **process launches** — demoted, per §8.
* Bytes transferred per correct extraction — matters for bandwidth-bound crawls, not for the core thesis.
* Wall-clock latency — report it, but it is concurrency-policy-dependent and easy to game; not a primary axis.
* Field-level accuracy, extraction failure rate (distinct from false success), unnecessary escalation, incorrect non-escalation.
* **Detection overhead** — dual-render cost attributable to learning, reported separately from steady state.

---

## 10. Fair Experimental Arms

The proposed A–E are close to fair. Three changes are needed.

**Arms**
* **A — HTTP-only.** Reference floor, not a competitor: it cannot escalate, so its correctness bounds what "no browser ever" buys.
* **B — Warm pooled Playwright.** The correctness ceiling and the cost baseline. Must use a persistent pool with Crawlee-like defaults, not a process per page.
* **C — Crawlee adaptive, default** (`result_checker` = `lambda _: True`).
* **D — Crawlee adaptive, naive checker** (e.g. "required keys present and non-empty"). **Split into D1 (checker only, i.e. Crawlee's real default wiring, comparison disabled per §4a) and D2 (checker + explicit `full_result_comparator`).** Without this split we would either flatter or slander Crawlee, and D1-vs-D2 independently quantifies the footgun.
* **E — our evidence/sufficiency checker**, supplied as a matched `(result_checker, result_comparator)` pair.
* **E0 — RAPTURE-style content-feature checker** (§7). New arm, and the one most likely to kill us: if 1999-vintage density features match our evidence model, our contribution is a citation.

**Fairness requirements**
1. **C, D1, D2, E, E0 must run inside the same Crawlee harness**, same extraction handler, same measurement wrapper. Otherwise we measure our implementation quality against Crawlee's, not our policy against theirs.
2. **Report cold-start and steady-state separately.** Crawlee's predictor is untrained at request 1 and returns `detection_probability_recommendation=1` while unsure; a short run measures its learning cost, a long run measures its steady state. Both are legitimate; conflating them is not.
3. **Fixed corpus order and seeded randomness.** `random()` at L384 makes runs non-deterministic; seed it and report variance across ≥3 repetitions.

---

## 11. Remaining Technical Gap

Narrower than `RESEARCH-GATE.md` claimed. Precisely:

1. **A sufficiency decision computed from the cheap document alone, that is measurably better than trivial or 2003-vintage alternatives.** Crawlee's cheap-path prediction reads only URL strings (Claim D); its verification hook is empty (Claim G); and supplying a checker disables the cross-mode comparison that would catch stale values (§4a). Whether a schema-and-provenance-based checker beats `required keys non-empty` or RAPTURE densities is **unknown and unmeasured**. That is the gap — and it is an empirical gap, not an architectural one.
2. **A benchmark that measures correctness against compute and separates confidently-wrong from failed.** Still nothing found. Crawlee's own three counters cannot answer it, and issue #2096 exists because nobody can currently measure this behavior.

Not a gap: the execution machinery, the escalation hook, the learning loop, or
verification-from-content-features as a technique.

---

## 12. Recommended Project Form

**OPTION 3 — CrawlBench first.**

Rejecting the others explicitly:
* **OPTION 1 (separate runtime)** — rejected. §5 found no architectural barrier; `result_checker` + `result_comparator` are sufficient injection points, and the browser pool, sub-crawler pipelines, and statistics already exist.
* **OPTION 2 (Crawlee-compatible library)** — deferred, not rejected. It is the right *form* for the decision layer, but writing it now would mean writing a policy with no way to tell whether it beats two lines of code. Gate it on arms D1/D2/E/E0.
* **OPTION 4 (upstream contribution)** — do the cheap part now, in parallel: the §4a comparator footgun and the #2096 findings are worth a well-evidenced upstream issue with a reproducing test, independent of whether we build anything. Low cost, immediate value, and it establishes standing with the maintainers.
* **OPTION 5 (stop)** — not yet warranted, because gap #2 is genuinely unfilled and cheap to fill.

---

## 13. Final Verdict

**BUILD CRAWLBENCH FIRST**

Every capability we proposed except the decision content already exists in
Crawlee at `v1.9.2`, and the decision content is expressible as a 50–200 line
`result_checker`, so there is no runtime to build — but there is also no way today
to tell whether a sophisticated checker beats a trivial one, which is exactly what
the missing benchmark would settle. Upstream issue #2096 and the
`create_default_comparator` footgun are third-party and code-level evidence that
adaptive-rendering decisions are silently miscalibrated in both directions and
that nobody can currently measure it. Build the measurement, run arms A–E0
including a RAPTURE-style baseline, and let the numbers decide whether the
sufficiency library is worth writing at all.

---

## 14. Addendum — Predictor Details Verified In Installed Source

Added 2026-08-17 during CrawlBench v0.2 Step 0. Environment: Python 3.12.13,
`crawlee==1.9.2`, `jaro-winkler==2.0.3`, `scikit-learn==1.9.0`, installed into the
project venv and read at
`site-packages/crawlee/crawlers/_adaptive_playwright/_rendering_type_predictor.py`.

**VERIFIED IN INSTALLED SOURCE**

* `jaro_winkler_metric` is not Crawlee's own code. It is `from jaro import jaro_winkler_metric`, supplied by the `jaro-winkler` distribution and pulled in by the `adaptive-crawler` extra alongside `scikit-learn`.
* `calculate_url_similarity` (L258–L278) uses `similarity_cutoff = 0.8`, returns 0 across hosts, 1 for identical component lists, and otherwise the mean over `zip_longest(..., fillvalue='')` of `1 if jaro_winkler_metric(a, b) > 0.8 else 0`.
* `get_url_components` (L250–L255) returns `[netloc, *path.strip('/').split('/')]`. **Query strings are discarded.** `/search?q=a` and `/search?q=b` therefore produce identical predictor input and compare as similarity 1. A query-parameterised URL set cannot form distinguishable family members.
* Before the model is fitted, `predict()` returns `rendering_type='client only'` with `detection_probability_recommendation=1`. The first request of any run is always browser-rendered and always dual-rendered.
* `labels_coefficients` is `defaultdict(lambda: n + 2)` with `n = 3`, i.e. it starts at 5 and `store_result` decrements it toward 1. With the default `detection_ratio=0.1`, a new label's detection probability decays 0.5 → 0.4 → 0.3 → 0.2 → 0.1 over its first four detections.
* §2 Claim D's description of the feature vector is confirmed: `_calculate_feature_vector` returns `(mean_similarity_to_static, mean_similarity_to_client_only)`, and `_calculate_mean_similarity` returns 0 when no URL of that class has been stored for the label.

**Correction to the v0.1 fixture analysis (BENCHMARK OBSERVATION, not source)**

An earlier CrawlBench analysis used a hand-written Jaro-Winkler approximation and
reported `stale-html-price ~ stale-hydration-overwrite = 0.813`, above the cutoff.
The real metric gives **0.6878**, below it. There is no accidental adversarial URL
pairing in the original fixture corpus. Measured with Crawlee's own function, the
eleven v0.1 fixture URLs have **zero pairwise similarity — 0 non-zero pairs out of
55** — so every feature vector is `(0, 0)` and the corpus cannot exercise URL-family
generalisation at all. Approximate implementations of a pinned dependency's metric
are not evidence; run the installed function.
