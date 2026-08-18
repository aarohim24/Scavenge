# SKILLS.md

Repeatable procedures for this repository. Each skill states when to use it, the
steps, and how you know it worked. Invoke them by name in conversation
("add a fixture", "measure an execution").

`CLAUDE.md` = how to behave. `AGENT.md` = what CrawlBench is. This file = how to
do the work.

Revised 2026-08-17: procedures now serve a benchmark, not a crawler.

---

## 1. Add A Fixture

**Use when** the benchmark needs a new page behavior.

Steps:
1. Write the page under `fixtures/pages/` so it is deterministic — no network, no
   clock dependence, no randomness. Delays are fixed and explicit.
2. Write ground truth **by hand**, independently of any tool output: task id,
   requested schema, expected record.
3. State which execution mode *should* suffice and why. That is the fixture's real
   assertion.
4. If the fixture has an adversarial variant — stale value, conflicting value,
   missing field — say what result state each arm must produce.

**Done when:** the fixture serves from local files, the test asserts against
hand-written ground truth, and it fails if extraction silently degrades.

**Never:** derive expected values from Playwright output. Playwright is an arm,
not an oracle.

---

## 2. Write An Extractor

**Use when** a fixture needs a field extracted.

Steps:
1. Support only the sources that fixture requires — DOM text, attributes, JSON-LD,
   embedded JSON / hydration state.
2. Keep it small. Extraction exists to make the benchmark meaningful, not to be a
   framework. No LLM, no embeddings, no self-healing selectors.
3. Where a field has multiple candidate sources in one document, return all of
   them. Conflicts are signal the benchmark needs, not noise to resolve early.
4. Raise on unexpected states. A missing field and a failed fetch are different
   outcomes and must stay distinguishable in the record.

**Done when:** the extractor handles the fixtures in the suite and nothing more.

---

## 3. Score A Result

**Use when** touching classification.

Steps:
1. Compare the extracted record to the expected record from ground truth. Nothing
   else is an input.
2. Classify deterministically as `CORRECT`, `FALSE_SUCCESS`, or `FAILED`. No
   confidence scores, no partial credit invented on the spot.
3. A complete, plausible, wrong record is `FALSE_SUCCESS` — never `FAILED`, never
   "succeeded." This distinction is the benchmark's reason for existing.
4. Test the adversarial fixtures first. `/stale-html-price` under HTTP must be
   `FALSE_SUCCESS`; the same fixture rendered must be `CORRECT`.

**Done when:** scoring depends only on (extracted, expected), and a test proves
Playwright output is not consulted as truth.

---

## 4. Measure An Execution

**Use whenever** a run produces numbers.

Steps:
1. Record per execution: `task_id`, `arm`, `result_state`, `extracted_record`,
   `expected_record`, `wall_time`, `cpu_time`, and — where reliably measurable —
   `peak_rss`, `bytes_transferred`, `request_count`, plus `browser_rendered` and
   `error_type`.
2. **If a metric cannot be measured consistently across HTTP and browser
   execution, mark it unsupported.** An unfair comparison is worse than a missing
   column.
3. Record environment metadata with every run: Python version, dependency
   versions, OS, architecture, and — once relevant — Crawlee, Playwright, and
   Chromium versions.
4. Write raw records as JSONL. Report components separately; never combine into an
   invented score.

**Done when:** a second person can rerun the same command and get the same record
structure, and every reported number traces to a row.

---

## 5. Keep The Browser Warm

**Use when** touching Playwright execution.

Steps:
1. One browser process for the whole run, reused across tasks. Never relaunch per
   task — that would make the baseline artificially expensive and every saving we
   report a fiction.
2. Measure the cost of a **browser-rendered navigation**, not process launches
   (`CONFIRMATION-PASS.md` §8).
3. Where practical, expose startup, page/context creation, and
   navigation/execution separately. Do not over-instrument in v0.1.
4. Tear the browser down even when a task raises.

**Done when:** a test proves the browser is reused rather than relaunched, and
another proves cleanup happens after an error.

---

## 6. Ship An Increment

**Use for** every change, without exception.

```
1. Say what is being implemented.
2. Say why it is necessary.
3. Implement minimally.
4. Add tests.
5. Run the tests.
6. Run format / lint / type checks.
7. Report actual results.
8. State remaining limitations.
```

**Done when:** the tests were run in this session and their real output was shown.

---

## 7. Turn A Bug Into A Regression Test

**Use whenever** something was wrong and is now fixed.

Steps:
1. Reproduce it as a failing test first, ideally as a fixture.
2. Fix it.
3. Confirm the test fails on the old code path if practical.

**Done when:** the test would catch the bug again.

---

## 8. Add A Benchmark Arm

**Use for** v0.2 and later (arms C, D1, D2, E0, E). Not for v0.1.

Steps:
1. Run it inside the same harness, with the same extraction handler, ground truth,
   and measurement wrapper as every other arm. Otherwise the result measures
   implementation quality, not policy quality.
2. Seed all randomness and report variance across ≥3 repetitions.
3. Report cold-start and steady-state separately for any arm that learns.
4. Record the exact version of any third-party system in the arm.
5. Report the arm's failures as faithfully as our own.

**Done when:** the comparison table lists versions and nothing in it is estimated.

**Never:** fabricate, round favorably, or omit an arm that beat us.

---

## 9. Prior-Art Check

**Use before** describing anything in this project as new.

Steps:
1. Primary sources only — pinned source at a recorded commit, official docs,
   issue trackers, papers. Blog posts are not evidence.
2. Read the actual release you claim to be reading. Verify the version came from
   the interpreter and index you think it did (`CONFIRMATION-PASS.md` §1 records
   how this went wrong once).
3. Classify each finding: VERIFIED IN CODE / VERIFIED IN DOCUMENTATION / VENDOR
   CLAIM / INDEPENDENT RESULT / RESEARCH RESULT / UNVERIFIED.
4. Check the specific question, not the general area: does the existing system do
   *this*, at *this* version?
5. If it already does it well — stop and report it.

**Done when:** every claim of difference has a link and a version next to it.

---

## Required Test Coverage

v0.1 is not complete until these pass:

```
static fixture scores correctly under HTTP
client-rendered fixture demonstrates an HTTP limitation
stale-price HTTP extraction is classified FALSE_SUCCESS
rendered stale-price extraction receives the correct ground-truth value
missing required fields classify as FAILED
scoring does not use Playwright as ground truth
HTTP and Playwright produce the same result model
Playwright browser is reused rather than relaunched per task
browser cleanup happens even after errors
raw benchmark results are reproducible in structure
```

---

## Anti-Skills

Things not to do here, however tempting:

* Using Playwright output as ground truth.
* Merging `FALSE_SUCCESS` into `FAILED`, or reporting it as success.
* Relaunching Chromium per task, or headlining "browser launches avoided."
* Inventing a combined score, or a confidence percentage.
* Adding an LLM to fix an extraction gap.
* Building the sufficiency policy (arm E) before D2 and E0 exist to beat.
* Implementing RAPTURE before the measurement foundation is trusted.
* Adding public-web URLs to v0.1.
* Introducing Rust, Redis, Postgres, Kubernetes, queues, or proxies.
* Building a separate crawler runtime — research found no architectural need.
* Describing CrawlBench as novel because we wrote it.
* Hard-coding expected benchmark numbers anywhere, including in tests.
