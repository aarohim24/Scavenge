# OSS MVP — Results

The first product increment, built after `DIAGNOSTIC-RETEST-RESULTS.md` returned
**BUILD OSS MVP — EVIDENCE ENGINE + MCP FIRST**. Historical reports are unchanged.

---

## 1. Product Definition

> A local, deterministic web-evidence engine that acquires and correlates a requested
> field's value across a page's representation channels and preserves exact provenance for
> every observation.

It answers *"where does this field appear, what does each representation contain, and how
do those values relate?"* — and stops there. Deciding which value is correct requires
knowing what the page means, which is the agent's or the developer's job.

## 2. Exact Differentiation

> **Deterministic field-level value correlation with provenance across webpage
> representation channels.**

Not claimed, all with prior art: HTTP fetching, browser automation, JSON-LD extraction,
structured-data inspection, endpoint discovery, XHR interception, raw-vs-rendered
comparison, scraping diagnosis generally, adaptive crawling, provenance generally, MCP.

## 3. Architecture

Two packages, not the three proposed — at this size a third was overhead.

```
evidence/          the engine; the only thing both interfaces call
  models.py        EvidenceReport, Observation, Relation, comparison keys
  engine.py        inspect_field(): acquire → observe → correlate
  acquire.py       HTTP, bounded browser render, JSON network capture
  channels.py      shared helpers: entity decoding, embedded JSON, key walking
  price.py         field adapter          availability.py  field adapter
  pricing.py       DOM/JSON-LD candidate selection      money.py  money parsing
  render.py        human-readable output  robots.py  safety.py
  mcp.py           MCP entry point — one tool

probe/cli.py       thin CLI over the same engine
```

**Dependency direction, verified mechanically:** `evidence/` imports **nothing** from
`realworld/`, `crawlbench/` or `probe/`. `probe/cli.py` → engine. `evidence/mcp.py` →
engine. `realworld/{money,extract}.py` → engine, via trivial re-export shims so the frozen
Arm E code and its tests keep working against one canonical implementation instead of a
drifting copy.

## 4. Evidence Model

```
EvidenceReport   schema_version · target · field · observations · relations
                 acquisition · warnings

Observation      id ("raw_dom:0") · channel · normalized_value · raw · provenance
                 status · note

Relation         left id · right id · EQUAL | DIFFERENT | UNCOMPARABLE
```

`normalized_value` is structured — `MoneyValue(amount, currency)` or
`AvailabilityValue(state)` — never an opaque string. A **private** `comparison_key()`
derives the hashable form correlation compares through, so the engine never learns what a
price is. That single indirection is what let a second field cost one module rather than a
second engine.

An absent channel is simply an absent observation; there is no `MISSING` relation and no
graph abstraction. Relations are cross-channel only — two candidates from one channel are
already visible as two observations.

## 5. Supported Fields

**`price`** and **`availability`**. Two, deliberately.

`price` carries every repair the retest validated: `Decimal` with explicit currency,
HTML-entity decoding at the probe boundary, locale-aware parsing, refusal to guess an
ambiguous separator, labelled extraction first with a conservative unlabelled fallback,
and **no election of a winner** — multiple candidates stay multiple observations.

`availability` normalizes only what it can read plainly: schema.org availability values
and clearly-labelled visible text. Anything else keeps its raw value and gets **no**
normalized value. There is no semantic `UNKNOWN` state, because we never observed one —
"Notify me when back in stock" and "Only 3 left" are tested to yield nothing.

## 6. Supported Channels

`RAW_DOM` · `STRUCTURED_DATA` · `EMBEDDED_STATE` · `RENDERED_DOM` · `NETWORK_JSON`.

**Not overstated:** the ten-target retest primarily exercised raw-DOM versus rendered-DOM
and found **no field-carrying JSON endpoint** in that sample. Five channels are
implemented and fixture-tested; five channels are not five channels' worth of real-world
validation.

## 7. Provenance Model

`Provenance(selector, pointer, script, request, content_type)` — populated per channel,
unused parts stay `None` and are omitted from JSON. DOM gives a selector path, structured
and embedded data give a JSON pointer plus script identity, network gives method, URL,
content type and pointer. Whole documents are never stored inside observations.

## 8. MCP Interface

One tool: `inspect_web_field(url, field)`, returning the report as structured data, not
prose. The description is factual and asserts the boundary — *"It reports evidence; it
does not decide which value is correct."* Errors (`unsupported_field`, `robots_refused`,
`unsafe_target`) are returned **as data**, never as a stack trace. The server reasons
about nothing and calls no model.

Built on the official SDK's `MCPServer` (`mcp` 2.0.0); the older `FastMCP` path no longer
exists in that release.

## 9. CLI Interface

```
probe inspect <url> --field price [--json] [--no-render]
```

It parses arguments, calls `inspect_field`, and prints. A test asserts the CLI's JSON is
byte-identical to the engine's, so the two interfaces cannot drift.

## 10. Security Boundaries

`http`/`https` only; `file://`, localhost, loopback, link-local and private ranges refused
before any request — verified through the real CLI path, with no test seam to bypass it.
Bodies capped at 512 KB, JSON responses capped at 40 with explicit overflow reporting,
bounded waits, bounded robots fetch. No captured request is replayed, no authenticated
request reissued, nothing from a page executed. Robots timeout or unreachability **never**
becomes permission, and `RobotFileParser.read()` / unbounded `urlopen()` are structurally
barred from re-entering the project by a test.

## 11. Files Changed

**New:** `evidence/{__init__,models,engine,acquire,channels,price,availability,render,mcp}.py`,
`tests/{test_engine,test_availability,test_mcp,test_cli,test_evidence_cases}.py`, `README.md`.
**Moved into `evidence/`:** `money.py`, price extraction (now `pricing.py`), `acquire.py`
(was `probe/observe.py`), `robots.py`, `safety.py`.
**Shims:** `realworld/money.py`, `realworld/extract.py` — re-exports plus Arm E's own
`compare_channels`, which stayed out of the engine.
**Rewritten:** `probe/cli.py` (thin). **Deleted:** `probe/{correlate,report,diagnose}.py`.
**Untouched:** all of `crawlbench/`, every historical result document.

## 12. Production LOC

```
new      847     models 193 · engine 137 · price 128 · availability 124
                 channels 75 · render 76 · mcp 62 · cli 52
moved    704     pricing 211 · acquire 181 · money 160 · robots 110 · safety 42
total  1,551
```

**This exceeds the ~1,000 ceiling and is flagged rather than glossed.** New code is 847,
under the line. The total is larger because proven code was **moved rather than copied**,
as directed — the alternative was two diverging parsers. No new abstraction was introduced
to reach it: an audit found no unused public name in `evidence/`, no single-use
abstraction, and one broad `except`, which is documented and converts a vanished response
body into evidence rather than a crash.

## 13. Dependencies

One added: **`mcp==2.0.0`** (official SDK). No agent framework, no LLM SDK, nothing else.

## 14. Test Results

```
before this increment:  173 passed
after:                  227 passed
ruff format --check     58 files already formatted
ruff check              All checks passed!
mypy                    Success: no issues found in 51 source files
```

Every historical test survived the move — the shims were verified green immediately after
each relocation, before any new code was written. New coverage: the evidence model and its
serialization, deterministic relations, multiple candidates preserved, absent channels,
partial render, acquisition failures, the observation cap warning, availability
normalization including the phrases it must refuse, MCP tool surface and error shapes, and
CLI-equals-engine.

## 15. MCP Smoke Test

Run over the **real stdio protocol** with the client SDK, not a unit test:

```
TOOLS: ['inspect_web_field']
KEYS:  ['error']
REFUSED (correct): {'kind': 'unsafe_target', 'detail': '127.0.0.1 resolves to non-public address'}
BAD FIELD:         {'kind': 'unsupported_field', 'detail': "field must be one of ['availability', 'price']"}
```

Tool discovery, invocation and error-as-data all work. The fixture server is on loopback,
which the safety layer correctly refuses — so a full report required a real URL.

## 16. Real-URL Smoke Test

One page, robots honoured, both fields, through MCP:

```
price:        3 observations, 3 relations, render=PARTIAL_RENDER
  RAW_DOM          0.00 USD   p (unlabelled)
  STRUCTURED_DATA  0.0  USD   script[1]/offers/0/price
  RENDERED_DOM     0.00 USD   p (unlabelled)
availability: 1 observation
  STRUCTURED_DATA  OUT_OF_STOCK   script[1]/offers/0/availability
```

**It found a real defect on the first real page.** `0.00` and `0.0` were reported as
`DIFFERENT`, because the comparison key stringified the amount. Fixed by keeping the
`Decimal` in the key, with a parametrised regression test (`0.00`/`0.0`, `99.00`/`99`,
`1234.50`/`1234.5` equal; `99.00`/`99.01` not). After the fix all three relations are
correctly `EQUAL`.

## 17. Known Limitations

1. **`availability` has essentially one real-world data point.** It is fixture-validated;
   the real-URL test exercised it on a single page.
2. **No sense of a blocked render.** A bot-challenge page returning HTTP 200 reads as a
   legitimate render — a blind spot the retest already recorded.
3. **Five channels, unevenly validated** (§6).
4. **Determinism is of report generation, not of the web.** Documented in the README
   rather than claimed away; the determinism test excludes timings for this reason.
5. **The distribution name is still `crawlbench`**, the retired name. Naming was
   explicitly out of scope for this increment.
6. **One real URL is not validation.** The `0.00`/`0.0` defect surfaced on the first real
   page tried, which is evidence that more such defects exist.

## 18. Research Claims We Do NOT Make

That this is novel scraping, adaptive crawling, endpoint discovery, structured-data
inspection, raw-vs-rendered comparison, provenance, or MCP. That it determines the correct
value. That it generalizes to arbitrary fields — two fields are implemented and one is
validated on real pages. That five-channel correlation is proven in the wild. That the
engine is faster or more complete than an agent at anything except deterministic
acquisition.

## 19. Naming Shortlist

**Deliberately not produced.** Naming and CI were excluded from this increment and belong
to release preparation. `probe` remains the internal codename; `crawlbench` is retired as
a product name and survives only as an unpublished distribution name.

## 20. MVP Verdict

All twelve success criteria are met except the LOC ceiling, which is explained by
relocation rather than by new machinery. One engine serves `price` and `availability`
across five channels with exact provenance and deterministic relations; rendering failures
degrade to evidence; unsafe targets are refused; CLI and MCP share one code path and are
tested to agree; JSON is stable and versioned; MCP works end-to-end over the real protocol;
the research record is intact and the engine depends on none of it.

Against that: the first real page exercised produced a correlation defect. It was small and
is fixed, but a single real URL cannot tell us how many more of its kind remain, and
`availability` has barely met the live web at all. Declaring release readiness on that
evidence would repeat exactly the mistake this project has spent every prior gate avoiding.

**MVP WORKS — NEEDS NARROW FIXES**

The narrow fixes are: validate `availability` on real pages, detect blocked renders, and
run enough real targets to find the next `0.00`/`0.0`. None requires new architecture.
