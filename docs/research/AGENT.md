# AGENT.md

What this repository is for, what is in scope, and what result would end it.
Read with `CLAUDE.md` (how to work) and `SKILLS.md` (procedures).

Revised 2026-08-17 after `RESEARCH-GATE.md` and `CONFIRMATION-PASS.md`.
Where this file conflicts with those reports, the reports win — they are pinned to
source, this file is a plan.

## What This Project Is

> **CrawlBench: a reproducible benchmark for measuring structured-extraction
> correctness against execution cost across HTTP and browser-based crawling
> strategies.**

It exists to answer one question with numbers:

> **What correctness and resource cost do different extraction/rendering
> strategies achieve on the same ground-truthed tasks?**

And through that, to decide a second question before any effort is spent on it:

> **Is a more sophisticated extraction-sufficiency policy worth building at all?**

## What This Project Is Not

It is **not** a novel adaptive crawler. That idea did not survive research.

Established, treat as project assumptions unless implementation shows otherwise:

1. Crawlee already supports adaptive HTTP/browser execution.
2. `result_checker` can gate acceptance of static extraction and, on failure, escalate to the browser.
3. `result_comparator` participates in rendering-type detection.
4. Crawlee's default rendering predictor is primarily URL-derived, not derived from evidence in the document at hand.
5. A custom sufficiency policy largely fits Crawlee's existing checker/comparator extension points.
6. Therefore **there is no justification for building a separate crawler runtime.**
7. Classical wrapper-verification research (RAPTURE, Kushmerick 1999/2000; Lerman–Minton–Knoblock, JAIR 2003) already verifies extraction from cheap signals.
8. Therefore **extraction verification itself is not novel** and must never be claimed as such.
9. What appears missing is a modern reproducible benchmark coupling structured-extraction correctness — including false success — with compute/resource cost across static and browser-rendered execution.
10. Whether a provenance/schema/conflict-aware sufficiency policy beats trivial validation or RAPTURE-style verification is **unknown**.

Point 10 is what CrawlBench measures. Everything else is settled or borrowed.

## Novelty Discipline

Building CrawlBench does not make CrawlBench novel. The defensible hypothesis is:

> Existing systems provide adaptive execution and classical research provides
> extraction verification, but we have not found a modern reproducible benchmark
> measuring structured-extraction correctness — including false success — against
> browser/compute cost.

That stays a hypothesis until the benchmark and prior-art work support it.

The *potential* future contribution is a cheap-document-only sufficiency policy
that materially outperforms trivial validation and classical wrapper verification
at deciding when browser rendering can safely be skipped. **It does not exist.**
Do not claim it until arm E beats D2 and E0 (see Roadmap).

## v0.1 Scope

Only these parts:

```
fixture server · ground truth · HTTP execution · warm pooled Playwright execution
structured extraction · measurement · scoring · result storage · report · tests
```

**Do not** implement adaptive crawling, our evidence-based checker, or RAPTURE in
v0.1. They come after the measurement foundation is trustworthy.

### Arms in v0.1

* **Arm A — HTTP.** Fetch without browser rendering, extract the requested fields.
* **Arm B — Warm Playwright.** Chromium through Playwright, **browser process kept alive across tasks**. Never a fresh process per page. This is the correctness/cost baseline.

Both arms share the same task, ground truth, result representation, scoring, and
measurement harness wherever practical.

## Fixtures

Deterministic and local. Nothing from the public web in v0.1 — live sites bring
network variance, geo differences, A/B tests, anti-bot behavior, site changes, and
rate limiting, all of which would be measured as if they were our signal. First
prove CrawlBench measures correctly.

```
/static-product      /jsonld-product     /client-rendered-product
/hydration-product   /stale-html-price   /conflicting-prices
/delayed-render      /missing-field      /table
```

Add a tenth only to test a specific measurement or correctness behavior.

### `/stale-html-price` is mandatory

Cheap document exposes `price = 2999`; rendered state produces `price = 1999`;
ground truth is `price = 1999`. An HTTP run returning `2999` must be classified
`FALSE_SUCCESS`, never "successful extraction." This fixture is the central
false-success problem in one page, and it is the reason the benchmark exists.

## Result States

Deterministic, three states, no confidence scores:

* **CORRECT** — the extraction produced the independently defined ground-truth record.
* **FALSE_SUCCESS** — the extractor returned a complete, plausible record that was wrong.
* **FAILED** — the extractor explicitly failed, returned incomplete required data, or did not claim a valid complete extraction.

`FALSE_SUCCESS` is the most serious outcome and is never merged into `FAILED`.

## Ground Truth

Independent of execution mode. Each fixture declares its expected structured
record; both arms are scored against that same record.

```json
{ "name": "Example Product", "price": 1999, "currency": "INR" }
```

**Never** define Playwright output as truth. Playwright is an arm, not an oracle.

## Extraction Scope

Deliberately minimal — extraction exists only to make the benchmark meaningful.
Support what the fixtures require: DOM text, HTML attributes, JSON-LD, embedded
JSON / hydration state. No universal extraction framework, no LLM, no embeddings,
no self-healing selectors.

## Measurement

Per execution record:

```
task_id · arm · result_state · extracted_record · expected_record
wall_time · cpu_time · peak_rss* · bytes_transferred* · request_count*
browser_rendered · error_type
```

`*` where reliably measurable. **If a metric cannot be measured consistently
across HTTP and browser execution, mark it unsupported rather than inventing an
unfair comparison.** Record environment metadata with every run: Python version,
dependency versions, OS, architecture, Crawlee version, Playwright version,
Chromium version.

### Primary metrics (eventually)

```
CPU-seconds per correct extraction
memory-seconds per correct extraction
browser-rendered navigations per 1,000 tasks
complete-record accuracy
false-success rate
```

For v0.1, implement only what can be measured correctly. Report raw measurements.
No arbitrary combined score.

### Browser cost model

Corrected by `CONFIRMATION-PASS.md` §8. **Do not optimize around Chromium process
launches** — Crawlee's own defaults amortize one launch over 20–100 navigations
(`max_open_pages_per_browser=20`, `retire_browser_after_page_count=100`), so
launches are a diagnostic, not a cost driver. The unit that matters is a
**browser-rendered navigation**, and the dominant memory term is retained RSS
occupancy of the warm pool.

Where practical, expose browser startup, page/context creation, and
navigation/execution separately — but do not over-engineer this in v0.1. The hard
requirement is simply: **never make Playwright artificially expensive by
relaunching per task.**

## Execution

One command does everything:

```
python -m crawlbench run
```

Start/use the fixture server → run Arm A → run Arm B → collect measurements →
score against ground truth → write machine-readable raw records (JSONL) → print a
concise summary. No database unless v0.1 actually needs one.

Report shape (illustrative only — **never hard-code expected results**):

```
CrawlBench v0.1
Tasks: 9

HTTP          Correct: …  False success: …  Failed: …
Playwright    Correct: …  False success: …  Failed: …

HTTP CPU/task: …   Browser CPU/task: …
HTTP p50 latency: …   Browser p50 latency: …
```

## Repository Shape

Guidance, not a mandate. Fewer modules is better; create nothing empty.

```
adaptive-extract/
├── crawlbench/
│   ├── execution/{http.py,playwright.py}
│   ├── extraction.py · scoring.py · measurement.py · models.py · cli.py
├── fixtures/{server.py,pages/}
├── tests/ · results/
├── pyproject.toml · README.md
└── CLAUDE.md · AGENT.md · SKILLS.md · RESEARCH-GATE.md · CONFIRMATION-PASS.md
```

## Environment

Project-local **Python 3.12**, not the machine default. The research pass showed
the system Python 3.9 silently resolves a year-stale Crawlee, which nearly
invalidated the entire prior-art review. Pin important dependencies. Conventional
tooling only — no elaborate environment management.

## Roadmap After v0.1

Preserved so the sequence is not re-litigated. Do not implement now.

* **v0.2** — Crawlee arms: **C** adaptive default; **D1** naive `result_checker` only (Crawlee's real default wiring, cross-mode comparison disabled); **D2** naive checker **plus** explicit `result_comparator`. D1-vs-D2 quantifies the comparator footgun in `CONFIRMATION-PASS.md` §4a.
* **v0.3** — **E0**, a RAPTURE-style verification baseline, reproduced faithfully enough to be a real competitor.
* **v0.4** — only then design **E**, provenance/schema/conflict-aware sufficiency. E must beat D2 and E0 meaningfully or it does not become a library.

Fairness rules for those arms: same harness, same handler, same measurement;
cold-start and steady-state reported separately; seeded randomness with variance
across ≥3 repetitions.

## Kill Criteria

Remain willing to stop.

* **E ≈ D2** or **E ≈ E0** within experimental noise → no justification for a sophisticated sufficiency library. Stop.
* HTTP plus cheap verification does not materially reduce CPU-seconds per correct extraction or browser-rendered navigations while preserving correctness → the runtime thesis fails. Stop.
* If milestone-0 measurement shows JS execution is not a dominant cost term, the thesis is dead on arrival — that is a good day, not a bad one.

CrawlBench may remain useful even when the runtime thesis fails. That is the point
of building it first.

## Out Of Scope

A Scrapy replacement, a separate crawler runtime, an autonomous browser agent, an
LLM scraping system, RAG, search, vector storage, CAPTCHA solving, anti-bot
bypass, proxy marketplace, distributed crawling, Kubernetes, a dashboard, a custom
browser, a generic workflow engine, self-healing selectors, public-web corpora in
v0.1.

## First Implementation Milestone

The vertical slice, and nothing beyond it:

```
one static fixture → HTTP fetch → extract → compare to independent ground truth
    → CORRECT / FALSE_SUCCESS / FAILED
```

No Playwright until that slice is reviewed.
