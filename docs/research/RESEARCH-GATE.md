# Research Gate Report — Adaptive Extraction-Aware Execution

Date: 2026-08-17. Author: engineering research pass, pre-implementation.
Constraints: `CLAUDE.md`, `AGENT.md`, `SKILLS.md`. No implementation code was written.

**Evidence classification used below:** VERIFIED IN CODE (read the source file),
VERIFIED IN DOCUMENTATION (official docs/API reference), VENDOR CLAIM,
INDEPENDENT RESULT, RESEARCH RESULT, UNVERIFIED.

**Methodology caveat, stated up front:** source files and docs were read through a
fetch-and-summarize layer, not line-by-line in a checkout. Every VERIFIED IN CODE
claim below should be re-confirmed by cloning the repo at a pinned commit before
any engineering decision is finalized. No claim here rests on a vendor benchmark
number.

---

## 1. Verdict

**PROCEED, BUT NARROW THE THESIS**

The general thesis — "adaptive HTTP/browser execution driven by extraction
results" — is **already implemented and shipped** by Crawlee, including the
learning and the extraction-result-based escalation hook. Building a new crawler
around that idea would be re-implementation.

Two things survive scrutiny and are worth building:

1. **A reusable, deterministic sufficiency-and-provenance layer** that decides
   whether HTTP output is trustworthy *without needing a browser run to compare
   against*. Crawlee provides the escalation hook and defaults it to
   "always sufficient"; nothing open-source fills that hook with real logic.
2. **A reproducible benchmark measuring extraction correctness against compute
   cost**, with false success separated from failure. No such benchmark appears
   to exist.

If the experiment shows Crawlee's existing URL-similarity predictor already
captures most of the available savings, this collapses to
**BUILD THE BENCHMARK ONLY**. That is a realistic outcome and should not be
resisted.

---

## 2. Closest Existing Competitor

**Crawlee `AdaptivePlaywrightCrawler`** (Python and JS). Not close — overlapping.

What it actually does, verified:

* Runs a static HTTP sub-crawler and a Playwright sub-crawler behind one
  request-handler interface, choosing per request via a `RenderingTypePredictor`.
  — VERIFIED IN DOCUMENTATION ([Python API](https://crawlee.dev/python/api/class/AdaptivePlaywrightCrawler), [guide](https://crawlee.dev/python/docs/guides/adaptive-playwright-crawler))
* **Decision is extraction-result-aware, not JS-detection-based.** `resultChecker`
  "is called on dataset items found by the request handler in plain HTTP mode…
  if it returns false, the request is retried in a browser."
  — VERIFIED IN DOCUMENTATION ([JS options](https://crawlee.dev/js/api/playwright-crawler/interface/AdaptivePlaywrightCrawlerOptions))
* In the Python implementation, the static run is executed, and only if
  `result_checker(static_run.result)` passes does it return early; otherwise
  control falls through to the browser handler.
  — VERIFIED IN CODE ([`_adaptive_playwright_crawler.py`](https://github.com/apify/crawlee-python/blob/master/src/crawlee/crawlers/_adaptive_playwright/_adaptive_playwright_crawler.py))
* **It compares extraction results across modes.** On sampled requests it runs
  *both* browser and HTTP and applies `result_comparator`; equal → site treated
  as static, different → client-rendered, `inconclusive` → sample discarded.
  Default comparator deep-compares `push_data` calls.
  — VERIFIED IN DOCUMENTATION + CODE
* **Decisions persist and learn, per URL cluster.** `DefaultRenderingTypePredictor`
  fits a scikit-learn logistic regression over a 2-feature vector: mean
  Jaro-Winkler similarity of the URL (domain + path segments) to known
  static URLs and to known client-only URLs, keyed also by request `label`.
  State is persisted via `RecoverableState` to key-value storage. Sampling rate
  is governed by `detection_ratio` (default 0.1) and decays as evidence
  accumulates for a label.
  — VERIFIED IN CODE ([`_rendering_type_predictor.py`](https://github.com/apify/crawlee-python/blob/master/src/crawlee/crawlers/_adaptive_playwright/_rendering_type_predictor.py))
* Explicit motivation is resource cost: it switches to HTTP-only "when it detects
  that it may bring a performance benefit." — VERIFIED IN DOCUMENTATION

Against the checklist in `AGENT.md`:

| Question | Crawlee |
|---|---|
| Decides HTTP vs browser | Yes — predictor + result checker |
| Compares extraction results across modes | Yes — `result_comparator` on sampled dual runs |
| Decisions persist / learn | Yes — persisted logistic regression |
| URL / domain / template specific | Yes — URL-similarity features + request label |
| Extraction evidence involved | **No** — dataset items only; no provenance |
| Optimizes resource cost | Intent yes; **no cost accounting or metrics** |
| Third tier (lightweight JS) | **No** — two modes |
| Sufficiency logic provided | **No** — `result_checker` defaults to `True` |

The last four rows are the only place our project can live.

**Closed-source competitor worth naming:** Zyte API states it "automatically
chooses the leanest technology possible… without any extra cost, and
automatically adapting to website changes," with ML-driven decisions users can
override. — VENDOR CLAIM, closed source, paid
([product page](https://www.zyte.com/zyte-api/), [browser docs](https://docs.zyte.com/zyte-api/usage/browser.html)).
Commercially this is the strongest evidence the problem is real *and* that the
value has largely been captured behind an API.

---

## 3. What Already Exists

* **Adaptive HTTP↔browser execution with learning** — Crawlee, shipped, both
  runtimes. SOLVED.
* **Escalation triggered by a check on the HTTP extraction result** — Crawlee
  `resultChecker` / `result_checker`. Mechanism SOLVED; policy empty.
* **Cross-mode result comparison to classify sites** — Crawlee
  `result_comparator`. SOLVED, though it defines the browser as truth.
* **Content-thinness fallback across engines** — Firecrawl's `scrapeURL`
  waterfall: engines are tried in a `buildFallbackList` order and an engine is
  rejected with `EngineUnsuccessfulError` when markdown is empty and the status
  code is good, terminating in `NoEnginesLeftError`.
  — VERIFIED IN CODE ([`scrapeURL/index.ts`](https://github.com/firecrawl/firecrawl/blob/main/apps/api/src/scraper/scrapeURL/index.ts)).
  This is presence-of-content, not correctness-of-value. PARTIAL and weak.
* **Sufficiency as a stopping criterion** — Crawl4AI's Adaptive Crawling scores
  coverage / consistency / saturation against a query and stops when
  `confidence_threshold` (default 0.8) is met.
  — VERIFIED IN DOCUMENTATION ([docs](https://docs.crawl4ai.com/core/adaptive-crawling/)).
  Different axis: *which pages to fetch*, not *which engine to use*. The concept
  of extraction sufficiency is therefore **not novel**, only its application to
  execution mode.
* **Self-healing selectors** — Scrapling. Out of scope per `AGENT.md`.
* **Cheaper browser runtime** — Lightpanda, CDP-compatible-in-progress.
* **Structured-extraction correctness benchmarks** — SWDE (80 sites, 124k pages,
  32 attributes, regex-derived ground truth), WCXB, ExtractBench (PDF→JSON),
  LiveWeb-IE (live sites). — RESEARCH RESULT. None measure compute.

---

## 4. What Remains Unsolved

Precisely two things.

**(a) Browser-free sufficiency with provenance.**
Crawlee's learning signal *requires the expensive mode*: it must dual-render a
sample to compare, and its cheap-path prediction is a function of **URL string
similarity**, not of the document in hand. Consequently a page whose HTTP output
is confidently wrong — stale JSON-LD price, a superseded server-rendered value, a
partial hydration payload — is caught only if that URL happens to fall in the
~10% detection sample. Nothing in the open-source ecosystem decides, *from the
cheap document alone*, whether the extracted values carry enough evidence to be
trusted: multi-source candidate agreement, conflicting-candidate detection,
schema and cardinality invariants, provenance recorded per value
(`source_type`, `source_location`, `document_hash`, `execution_mode`).
Status: **UNSOLVED**, searched seriously (Crawlee code, Scrapling docs, Firecrawl
code, Crawl4AI docs, Katana README, scrapy-playwright docs, plus prior-art
searches for extraction provenance and cost-aware crawling).

**(b) A correctness-versus-compute benchmark.**
Every benchmark found measures accuracy only. SWDE is static 2011 snapshots with
no JavaScript dimension; ExtractBench is PDFs; LiveWeb-IE evaluates live-site
extraction but the abstract discusses no compute, rendering-mode, or
browser-usage metrics. No benchmark reports CPU-seconds, peak RSS, bytes, browser
launches, or cost per correct record — and none separates *failed extraction*
from *confidently wrong extraction*. Status: **UNSOLVED**.

### Capability table

| Capability | Status |
|---|---|
| HTTP/browser adaptive execution | **SOLVED** (Crawlee) |
| HTTP → lightweight JS → Chromium escalation | **PARTIAL** (two-tier solved; third tier blocked on Lightpanda maturity, not on ideas) |
| Extraction-aware escalation | **PARTIAL** (hook + comparator shipped; no sufficiency policy, no browser-free judgment) |
| Evidence / provenance extraction | **UNSOLVED** in crawling frameworks |
| Self-healing extraction | **SOLVED** (Scrapling) — out of scope |
| Cost-aware execution optimization | **PARTIAL** — intent in Crawlee, claimed in Zyte (closed), no open measurement or optimization target |
| Reproducible correctness-vs-compute benchmark | **UNSOLVED** |

---

## 5. Why It Remains Unsolved

**Evidence-based:**

* Crawlee deliberately made sufficiency the *user's* problem: `result_checker`
  "by default, it always returns `True`" (VERIFIED IN DOCUMENTATION). The
  framework's job ends at the hook. A framework cannot know a caller's schema.
* Crawlee's default comparator compares `push_data` calls — a generic structural
  equality, the only thing possible without knowing field semantics.
* Firecrawl's check is `markdown.trim().length > 0` (VERIFIED IN CODE) — the
  cheapest signal that generalizes across arbitrary pages.
* Lightpanda's own docs describe Web API support and CDP compatibility as
  partial/WIP, and there are open issues where Playwright breaks against it
  (e.g. missing CDP navigation `timing.startTime`) — so a mature third tier has
  not been available to build against.
  ([docs](https://lightpanda.io/docs/), [issue #2199](https://github.com/lightpanda-io/browser/issues/2199))

**Engineering inference, labeled as such:**

* Provenance is an *API-shape* commitment. Returning `ExtractedValue` instead of
  a scalar changes every extraction call site, so mature frameworks with
  compatibility obligations avoid it.
* Measuring CPU-seconds and RSS per extraction is unglamorous and hard to make
  reproducible across machines; there is no leaderboard incentive, unlike
  accuracy benchmarks.
* The economic incentive to solve (a) well sits with vendors who bill per
  request — Zyte's automatic-leanest-technology selection is exactly the feature
  you monetize rather than open-source.
* It is genuinely possible the residual value is small, because a warm browser
  pool is much cheaper than a cold launch. This is failure mode #2 below and the
  experiment must be able to conclude it.

---

## 6. Strongest Novelty Claim We Can Honestly Make

Crawlee already performs adaptive HTTP/browser execution, already escalates on an
extraction-result check, and already learns and persists per-URL-cluster
decisions; Crawl4AI already frames crawling in terms of information sufficiency;
Scrapling already relocates elements; Zyte already sells automatic
leanest-mode selection. What does not appear to exist in the open is a
deterministic sufficiency judgment made *from the cheap document alone* — using
per-value provenance and cross-source agreement rather than a sampled comparison
against a browser run — together with a benchmark that measures extraction
correctness against CPU, memory, bandwidth and browser launches, and that scores
confidently-wrong extraction separately from failed extraction. The claim is
about the decision policy and its measurement, not about adaptive crawling.

---

## 7. Strongest Reasons We May Fail

Ranked.

1. **The remaining delta over Crawlee is small.** Crawlee's URL-similarity
   predictor plus a caller-written `result_checker` may already capture most of
   the achievable savings on real workloads. If our sufficiency layer only
   improves the tail, the honest deliverable is a `result_checker` contribution
   and a benchmark — not a project.
2. **Warm browser pools erase the prize.** The expensive thing is *launching*
   Chromium, not *using* it. A persistent context pool amortizes launch cost
   across hundreds of navigations, so "Chromium launches avoided" may be a
   near-meaningless metric and the real per-page delta may be small enough that
   nobody trades correctness risk for it. **The benchmark must measure a warm
   pool as the primary baseline, not cold launches** — measuring cold launches
   would be the single easiest way to fake a good result.
3. **False sufficiency is fundamentally hard to detect one-sided.** Deciding
   "HTTP is trustworthy" without a browser reference is, in the worst case,
   undecidable: a server-rendered value can be silently superseded by JS with no
   trace in the HTTP document. Multi-source agreement fails exactly when all
   cheap sources derive from the same stale server state. Our headline metric
   could hold only because our fixtures leave a trace.
4. **Detection cost approaches execution cost.** Parsing every candidate source
   (JSON-LD, all embedded JSON, hydration blobs) on every page, plus invariant
   checks, is real CPU. On heavy pages, exhaustive candidate extraction plus an
   eventual escalation costs *more* than going straight to the browser. Our
   design must be measured against "always browser" including our own overhead
   on escalated pages.
5. **Benchmark bias and site non-stationarity.** A hand-picked corpus drifts
   toward JSON-LD-rich e-commerce, which flatters HTTP. And learned/template
   decisions decay under deploys, A/B tests, personalization, and geo variation
   — a result measured once is not a result that holds in production.

Also noted, lower ranked: Lightpanda's compatibility gap may make tier 2 either
unusable or, once compatible enough, expensive enough that tier 2 stops paying
for itself; and anti-bot behavior means HTTP and browser modes are not
substitutable on many real sites regardless of extraction quality.

---

## 8. Falsification Experiment

Smallest design that can produce a negative result.

**Dataset.** Two layers.
*Layer 1 — deterministic local fixtures*, served from the filesystem, the nine in
`AGENT.md`. Purpose: prove the mechanism and, critically, prove the harness can
*detect* false success. `stale-html-price` and `conflicting-prices` are the load-
bearing cases.
*Layer 2 — 60–100 public URLs*, stratified deliberately against our own interest:
~⅓ static/JSON-LD-rich, ~⅓ client-rendered, ~⅓ hybrid/hydrated, drawn from more
than one vertical (not only e-commerce). Snapshot every response to disk with its
hash so runs are replayable and the corpus is auditable for bias.

**Execution modes.** `HTTP` and `CHROMIUM` only for the first result. Chromium is
measured in **two configurations — cold launch per page and a warm persistent
context pool** — because failure mode #2 decides the project. `LIGHTWEIGHT_JS`
is added only after the two-tier number exists, and only if Lightpanda runs the
corpus at all.

**Ground truth.** Hand-authored per task: fixture/URL, requested schema, expected
values, and the mode that *should* suffice. Playwright output is never the label.
For Layer 2, annotate from a browser session by human reading, then freeze the
snapshot so the label stays valid.

**Metrics.**
Correctness: field accuracy, complete-record accuracy, **false-success rate**,
extraction failure rate — the last two never merged.
Resources: wall-clock, CPU-seconds (`resource.getrusage`), peak RSS,
memory-seconds where practical, bytes transferred, request count.
Execution: minimum sufficient mode, Chromium launches, launches avoided,
unnecessary escalation (escalated when HTTP was already correct), and
**incorrect non-escalation** (stopped at HTTP while wrong) — the metric that can
kill the thesis.

**Methodology.** One machine, versions pinned and logged, fixed concurrency and
timeout policy, alternating run order, three repetitions per configuration
reporting median and spread. Persist every execution record to SQLite. Report
components separately; no combined score.

**Mandatory comparison arm:** Crawlee `AdaptivePlaywrightCrawler` on the same
corpus and tasks, in three settings — default `result_checker`, a naive
hand-written checker, and our sufficiency layer plugged in as the checker. If our
layer does not beat the naive checker, we have our answer.

---

## 9. Go / No-Go Thresholds

Measured on Layer 2 against the **warm-pool** Chromium baseline.

**CONTINUE**
* ≥98% of Chromium-baseline field and complete-record accuracy, AND
* ≥50% fewer Chromium executions OR ≥2× better compute cost per correct
  extraction (CPU-seconds primary), AND
* false-success rate ≤1% absolute and no worse than the Chromium baseline, AND
* our sufficiency layer measurably beats Crawlee's default and naive-checker arms
  on at least one of correctness or compute at parity on the other.

**RETHINK**
* Correctness holds (≥98%) but savings land in 20–50% / 1.2–2×, or
* savings are large but false success rises above 1%, or
* we match Crawlee's arms rather than beating them.
Then narrow to a defensible slice — JSON-LD and structured-data extraction,
documentation crawling, or the benchmark alone — and re-gate. Do not default to
building the general crawler.

**STOP**
* <20% of Chromium executions avoided or <1.2× compute improvement, or
* correctness retention <98%, or false success materially worse than baseline, or
* sufficiency detection CPU approaches browser CPU on the escalated set, or
* Crawlee's existing predictor plus a trivial checker matches us within noise,
  in which case contribute the checker upstream and keep the benchmark.

---

## 10. Minimal Implementation Plan

Experiment only. Each step ends with tests run and real output reported.

1. **Benchmark skeleton.** Fixture server, task/ground-truth schema, SQLite
   execution records, resource measurement (CPU, RSS, bytes) wrapper. Test:
   metrics recorded correctly; a deliberately wrong extractor is scored as
   false success, not failure.
2. **Nine fixtures with hand-written ground truth.** Test: each fixture serves
   deterministically and its label is independent of any tool output.
3. **`fetch(url, mode)` for HTTP and CHROMIUM**, providers independent of
   extraction, warm-pool and cold-launch Chromium variants. Test: browser
   processes are cleaned up.
4. **Extraction with provenance.** Candidate enumeration across JSON-LD,
   embedded JSON, hydration state, attributes, DOM text; all candidates returned
   as `ExtractedValue`. Test: evidence points to the correct source.
5. **Sufficiency decision.** Deterministic rules → SUFFICIENT / AMBIGUOUS /
   INSUFFICIENT plus an escalation reason. Test: conflicting → AMBIGUOUS,
   missing → INSUFFICIENT, both escalate; stale-price fixture must not return
   SUFFICIENT.
6. **First result: fixtures end to end**, HTTP → decide → escalate → Chromium,
   with the full metric table printed.
7. **Layer 2 corpus (60–100 URLs) with snapshots**, then the same table.
8. **Crawlee comparison arm.** Report all three settings.
9. **Gate review against §9.** Only then consider Lightpanda as tier 2.

Nothing beyond this. No production architecture, no self-healing selectors, no
LLM.

---

## 11. Free-Tier Feasibility

Runs locally for **$0**. Dependencies: `httpx`, Playwright + Chromium (free
download, local), `lxml` or `selectolax`, Pydantic, stdlib `sqlite3`,
`resource`/`psutil` for CPU and RSS, `pytest`, `ruff`, `mypy`. Crawlee-Python for
the comparison arm is open-source and pulls scikit-learn (already its
dependency). Lightpanda is a free open-source binary — evaluate, do not assume.
No Rust, no Redis, no Postgres, no Kubernetes, no proxies, no paid APIs, no LLMs.

Unavoidable non-cash costs: disk for snapshots (small — tens of MB for 100 URLs),
and **human annotation time** for Layer 2 ground truth, which is the real budget
line and the main reason to keep the corpus at 60–100 URLs. Firecrawl's
self-hosted comparison needs Docker and may need an API key for its cloud
engines; keep it optional and only include it if a fair free self-hosted
configuration exists.

---

## 12. Sources

Primary, strongest first.

* Crawlee Python — [`_rendering_type_predictor.py`](https://github.com/apify/crawlee-python/blob/master/src/crawlee/crawlers/_adaptive_playwright/_rendering_type_predictor.py) (VERIFIED IN CODE)
* Crawlee Python — [`_adaptive_playwright_crawler.py`](https://github.com/apify/crawlee-python/blob/master/src/crawlee/crawlers/_adaptive_playwright/_adaptive_playwright_crawler.py) (VERIFIED IN CODE)
* Crawlee JS — [`AdaptivePlaywrightCrawlerOptions`](https://crawlee.dev/js/api/playwright-crawler/interface/AdaptivePlaywrightCrawlerOptions) (VERIFIED IN DOCUMENTATION — `resultChecker` → browser retry)
* Crawlee Python — [Adaptive Playwright crawler guide](https://crawlee.dev/python/docs/guides/adaptive-playwright-crawler) and [API class](https://crawlee.dev/python/api/class/AdaptivePlaywrightCrawler) (VERIFIED IN DOCUMENTATION)
* Firecrawl — [`scrapeURL/index.ts`](https://github.com/firecrawl/firecrawl/blob/main/apps/api/src/scraper/scrapeURL/index.ts) and [`engines/`](https://github.com/firecrawl/firecrawl/tree/main/apps/api/src/scraper/scrapeURL/engines) (VERIFIED IN CODE — thin-content waterfall)
* Crawl4AI — [Adaptive Crawling](https://docs.crawl4ai.com/core/adaptive-crawling/) (VERIFIED IN DOCUMENTATION — query-sufficiency, different axis)
* Scrapling — [Fetchers API reference](https://scrapling.readthedocs.io/en/latest/api-reference/fetchers.html) (VERIFIED IN DOCUMENTATION — explicit fetcher choice; no automatic escalation found. Source not read; treat as documentation-level only)
* Katana — [README](https://github.com/projectdiscovery/katana) (VERIFIED IN DOCUMENTATION — `-headless` is a user flag; hybrid crawling is opt-in)
* scrapy-playwright — [README](https://github.com/scrapy-plugins/scrapy-playwright) (VERIFIED IN DOCUMENTATION — per-request `meta["playwright"]`, manual)
* Lightpanda — [docs](https://lightpanda.io/docs/) (partial Web API / WIP CDP) and [issue #2199](https://github.com/lightpanda-io/browser/issues/2199) (Playwright CDP gap). Performance figures (11× faster, 9× less memory) are VENDOR CLAIM — not used in any reasoning above.
* Zyte API — [product page](https://www.zyte.com/zyte-api/), [browser docs](https://docs.zyte.com/zyte-api/usage/browser.html) (VENDOR CLAIM, closed source)
* Benchmarks — [SWDE](https://academictorrents.com/details/411576c7e80787e4b40452360f5f24acba9b5159) (RESEARCH RESULT), [ExtractBench](https://arxiv.org/abs/2602.12247), [LiveWeb-IE](https://arxiv.org/pdf/2603.13773), [WCXB](https://arxiv.org/pdf/2605.21097) — none measure compute cost or rendering mode

**Searched and found nothing closer:** academic work on "when to render" /
cost-aware rendering decisions for crawlers (searches returned vendor blogs only,
no peer-reviewed work); crawler benchmarks ranked by correctness-per-compute;
provenance-carrying extraction in crawling frameworks. Absence of evidence after
this much searching is weak evidence of absence — one more pass through arXiv
(IR/web-mining venues) and the Crawlee issue tracker is warranted before the
UNSOLVED labels are treated as settled.
