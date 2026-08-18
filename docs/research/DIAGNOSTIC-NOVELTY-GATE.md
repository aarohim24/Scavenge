# Diagnostic Novelty Gate

A narrow prior-art pass for one product form only: **a local CLI that inspects a single
URL and explains, with evidence, how it can most reasonably be scraped.** No
implementation code was written or modified. Date: 2026-08-18.

This does not repeat the crawler/runtime research in `RESEARCH-GATE.md`,
`CONFIRMATION-PASS.md` or `NOVELTY-GATE.md`. It asks one question: *does this tool
already exist?*

Evidence classes: **VERIFIED IN DOCUMENTATION** (official docs, README, package
metadata read directly), **VERIFIED IN CODE**, **VENDOR CLAIM**, **NEGATIVE RESULT**
(searched, found nothing), **ENGINEERING INFERENCE**.

---

## 1. Verdict

**PROCEED — DIFFERENTIATION NARROWED.**

Close tools exist and two of them are closer than expected. The differentiation that
survives is narrower than the brief's hypothesis and must be stated exactly:

> **Deterministic, local, field-level value correlation across raw HTML, structured
> metadata, embedded state, rendered DOM and network JSON — with provenance for every
> value — producing a reproducible report.**

Not "a scrape-target diagnostic." Diagnosis in general is occupied. What is unoccupied
is doing it *deterministically, locally, and per requested field value*.

Three capabilities from the brief's list are hereby **conceded to prior art and must
never be claimed**: network/API endpoint discovery (B), raw-vs-rendered HTML comparison
(C), and structured-data inspection (A). We reuse all three; we contribute none.

---

## 2. What Was Searched

GitHub (repository search via the API, several phrasings), PyPI (JSON metadata read
directly), the npm registry search API, and web search by *functionality* rather than
terminology — "tell me if I need a browser", "find the hidden JSON endpoint", "compare
view-source to the DOM", "scraping plan for a target". Named targets from the brief were
each checked: `api_hunter_cli`, Scrapling, Scrapy, Crawlee, Playwright, Chrome DevTools
automation, HAR tooling, JSON-endpoint discovery, JS-rendering checkers, structured-data
inspectors, Firecrawl, Zyte, Apify, Crawl4AI.

**NEGATIVE RESULT worth recording:** GitHub repository search for the conjunction of
diagnosis + representation comparison returns *nothing* — zero results for
`scraping diagnostic raw rendered network endpoints report`,
`javascript rendering detector scraping`, and `hidden api finder scraping`. The word
"recon" in this space is owned by security/OSINT tooling, not by data-representation
analysis. The npm registry returns no diagnostic tool at all.

---

## 3. Closest Prior Art

### 3.1 `browser-recon` (PyPI, v0.3.9, active) — closest in product *form*

VERIFIED IN DOCUMENTATION (PyPI JSON metadata read directly). Self-described as
"Reconnaissance for production scrapers… returns a verified scraping plan". Input is a
URL, output is a report. That is our shape.

What it actually reports: which anti-bot vendor protects the target; which captured
endpoints carry data vs. are session prerequisites vs. noise; which HTTP library × proxy
tier combination worked under live test requests; the minimum required headers and
cookies; a measured safe rate-limit; and runnable starter code.

Why it does not close the gap:

- **Its axis is transport, ours is representation.** It answers *"how do I get a
  successful response?"* — anti-bot, headers, cookies, proxies. It does not answer
  *"where does the value I want live, and do the copies of it agree?"* It never inspects
  JSON-LD, embedded state, or raw-vs-rendered differences.
- **It is not local.** "All processing runs on the browser-recon server. The CLI is a
  thin client… no detection rules, no validation logic, no LLM prompts, no scoring
  heuristics live on your machine." It requires `recon login` and an API key. Every
  target you inspect is uploaded. That is precisely the constraint the diagnostic form
  was supposed to relieve.
- **It is interactive and human-paced.** "You browse the target site for a couple of
  minutes — click on what you care about." It is not `inspect <url>`.
- **It uses an LLM server-side** ("no LLM prompts live on your machine" implies they
  live on theirs; "grounded in what worked, not in what the LLM expected to work").

**Overlap conceded:** endpoint inventory and endpoint classification. We must not claim
that capability.

### 3.2 `chrome-devtools-mcp` (Google, official, ~34K stars) — closest in *capability*

VERIFIED IN DOCUMENTATION. Gives an LLM agent a live Chrome over CDP:
`list_network_requests`, `get_network_request`, DOM access, performance traces. An agent
holding this tool can perform the entire DevTools workflow, including finding the JSON
endpoint and noticing that raw HTML lacks a value.

**This is the strongest "it already exists" finding in this pass, and it is the honest
answer to "why not just ask an agent?".** It is also the reason our claim must be
*deterministic*, not *diagnostic*: it is a control surface, not a report. It produces no
reproducible artifact, performs no value correlation, gives no provenance, and its
answers vary with the model. Our project constitution forbids an LLM in the data path
(`CLAUDE.md` §6), so this is a genuinely different object — but a developer choosing
between the two will often reasonably choose the agent.

### 3.3 `yfe404/web-scraper` (Claude Code skill) — the workflow, already automated by prompting

VERIFIED IN DOCUMENTATION. Implements almost exactly the flow the brief describes:
Phase 0 fetches raw HTML, detects the framework (e.g. Next.js via `__NEXT_DATA__`),
searches for the data points, then hits a quality gate — *"All data in HTML?"* — and if
yes, **skips the browser entirely**.

That is our decision rule, shipped, today. The differences are that it is an LLM prompt
rather than a program: non-deterministic, unreproducible, no provenance, no
disagreement detection, and no report the developer can diff between runs. It is strong
evidence that the *workflow* is well-known and that people are automating it — with
prompts, because no deterministic tool exists.

### 3.4 The rest

| Tool | Capability | Why it does not close the gap |
|---|---|---|
| `api_hunter_cli` | **B** only | Playwright captures JSON responses to two files. Explicitly no raw-vs-rendered comparison, no field correlation, no structured data, no strategy. GET only. (VERIFIED IN DOCUMENTATION) |
| Scrapling `capture_xhr` | **B**, as a library primitive | You pass a URL *pattern* — you must already know what you are looking for. It is a fetching feature, not a diagnosis. (VERIFIED IN DOCUMENTATION) |
| `extruct` | **A** only | Returns JSON-LD/Microdata/RDFa side by side and deliberately does not compare or validate them. Established in `NOVELTY-GATE.md` §7. |
| "View Rendered Source" extension, diff tools | **C** only | Line-by-line HTML diff — exactly the noise the brief tells us to avoid. Not field-level, browser-only, no network, no strategy. |
| JS-rendering checker web tools | one bit of **C** | "Does this page need JS?" and nothing else. |
| Scrapfly CLI | scrape/extract/screenshot | A client for a paid API's operations. It does not diagnose a target for you. (VENDOR CLAIM) |
| Firecrawl / Zyte / Apify | runtime rendering decisions | Firecrawl "automatically decides on-the-fly whether it needs a headless browser"; Zyte selects the leanest technology. Both decide **internally and silently**. Neither explains the target to the developer. This is arm C of the old project, not a diagnostic. (VENDOR CLAIM) |
| Crawlee `AdaptivePlaywrightCrawler` | runtime | Automates the runtime decision from URL similarity; tells the developer nothing. Already verified in `CONFIRMATION-PASS.md`. |
| Scrapy docs workflow | the manual baseline | Prescribes the workflow by hand and concedes it "may not seem efficient in developer time". This is the pain, not a tool. |

---

## 4. Capability Matrix

Using the brief's own A–E split.

| | A structured data | B network/API discovery | C raw-vs-rendered | D field-value provenance & disagreement | E combined strategy report |
|---|---|---|---|---|---|
| `extruct` | ✅ | — | — | — | — |
| `api_hunter_cli` | — | ✅ | — | — | — |
| Scrapling | partial | ✅ (pattern-driven) | — | — | — |
| View Rendered Source | — | — | ✅ (line diff) | — | — |
| JS-rendering checkers | — | — | ✅ (one bit) | — | — |
| `browser-recon` | — | ✅ | — | — | ✅ **transport axis only** |
| `chrome-devtools-mcp` + agent | ✅ | ✅ | ✅ | ~ (LLM judgement) | ~ (LLM judgement) |
| `yfe404/web-scraper` skill | ✅ | ✅ | ✅ | — | ~ (LLM judgement) |
| Firecrawl / Zyte / Crawlee | — | — | — | — | internal, never shown |
| **Proposed prototype** | ✅ reused | ✅ reused | ✅ field-level | ✅ **deterministic** | ✅ **deterministic, local** |

**Column D is the only one with no deterministic entry.** That is consistent with
`NOVELTY-GATE.md` §11, which found the same column empty in the runtime framing — the
finding survives the change of product form, which is mild evidence it is real rather
than an artifact of how we phrased the search.

The second unoccupied cell is the *conjunction*: no non-LLM tool produces E at all.

---

## 5. Novelty Standard — Applied Against Ourselves

The brief's test is that "nobody bundled these libraries together" is not sufficient.
Applying it honestly:

- **Bundling A + B + C is not our contribution.** An agent with `chrome-devtools-mcp`
  already does it, and the `web-scraper` skill already scripts it. If the prototype
  merely printed structured data, endpoints and a rendered diff, this gate should have
  returned **STOP DIAGNOSTIC**.
- **What is not bundling is D.** Every tool above surfaces *representations*. None
  correlates a *value* across them and reports where the copies disagree, with the path
  each came from. That requires the locale-correct normalisation and provenance
  machinery we already built and validated, and it is the piece an LLM does unreliably
  and a line-diff cannot do at all.
- **The proposed claim wording, amended to what the evidence supports:**

  > *A local, deterministic scrape-target diagnostic that correlates a requested field's
  > value across raw HTML, structured metadata, embedded state, rendered DOM and network
  > JSON, and reports where those representations disagree.*

  The brief's draft wording — "correlates raw representations, rendered state and network
  responses to explain which extraction path is worth investigating" — is **too broad and
  must not be used**: `browser-recon` explains an extraction path, and an agent with
  DevTools MCP correlates representations. The words *local*, *deterministic* and *a
  requested field's value* are load-bearing and may not be dropped.

---

## 6. The Strongest Case For STOP, Recorded

Stated as forcefully as I can, because the gate is worthless otherwise:

1. **The real 2026 baseline may not be manual DevTools.** It may be a developer asking an
   agent with `chrome-devtools-mcp` — 34K stars, weekly releases, official Google. If
   that answers the question in two minutes, our fifteen-minute manual baseline flatters
   us, and the ten-target experiment would measure the wrong comparison.
2. **`browser-recon` exists and is being actively developed**, which is evidence someone
   with commercial motivation surveyed this space and concluded the valuable axis is
   anti-bot and transport — the axis we have refused to work on — not representation.
3. **D may be unoccupied because it is not worth occupying.** `NOVELTY-GATE.md` §10 and
   §13 already established that in the wild, representation disagreement usually means
   stale markup or sale-vs-list pricing rather than a wrong cheap extraction. As a
   *decision* that killed arm E's confidence story. As a *report to a human* it may
   simply be a line the developer skips.

**Why PROCEED anyway:** the counter to (3) is the one thing the pivot actually changes —
a human adjudicates, so no precision threshold is needed, and being *interesting* is a
lower bar than being *right*. The counter to (1) and (2) is that determinism, locality
and reproducibility are real properties an LLM-mediated answer does not have, and they
are cheap for us because the machinery exists. But (1) is a live risk and the ten-target
experiment must record an agent baseline alongside the manual one, or its result will not
mean what we want it to mean.

---

## 7. Consequences For the Prototype

Binding on the implementation that follows:

1. **Do not build A, B or C as contributions.** Reuse `extruct`-equivalent parsing we
   already have, and Playwright's existing network events. Keep them minimal.
2. **D is the prototype's centre.** Correlation and provenance get the engineering
   attention; everything else is plumbing.
3. **The report must be deterministic** — same page, same bytes, same report. This is the
   differentiator; if the output varies run to run, we have built a worse agent.
4. **The recommendation must advise, never assert** (`CLAUDE.md` §7, brief §9).
5. **Record an LLM-agent baseline** in the ten-target experiment, not only the manual
   DevTools baseline, per §6(1).
6. **Naming:** `CrawlBench` is retired for the product per `DEVELOPER-PAIN-GATE.md` §23.
   The prototype uses the temporary internal codename **`probe`** with no registry claim,
   no branding, and no marketing. Public naming is deferred until after the ten-target
   result; spending time on it before then would be premature.

---

## 8. Sources

- browser-recon — https://pypi.org/project/browser-recon/ (VERIFIED IN DOCUMENTATION; package metadata read via the PyPI JSON API)
- chrome-devtools-mcp — https://github.com/ChromeDevTools/chrome-devtools-mcp (VERIFIED IN DOCUMENTATION)
- api_hunter_cli — https://github.com/engcarlosperezmolero/api_hunter_cli (VERIFIED IN DOCUMENTATION)
- Scrapling — https://scrapling.readthedocs.io/ , https://github.com/D4Vinci/Scrapling (VERIFIED IN DOCUMENTATION)
- yfe404/web-scraper Claude skill — https://github.com/yfe404/web-scraper (VERIFIED IN DOCUMENTATION)
- extruct — https://github.com/scrapinghub/extruct (VERIFIED IN DOCUMENTATION, via NOVELTY-GATE.md §7)
- View Rendered Source — https://chromewebstore.google.com/detail/view-rendered-source/ejgngohbdedoabanmclafpkoogegdpob (VERIFIED IN DOCUMENTATION)
- Scrapy, *Selecting dynamically-loaded content* — https://docs.scrapy.org/en/latest/topics/dynamic-content.html (VERIFIED IN DOCUMENTATION)
- Scrapfly CLI — https://scrapfly.io/products/scrapfly-cli (VENDOR CLAIM)
- Firecrawl vs Apify comparison, rendering auto-decision — https://blog.apify.com/firecrawl-vs-apify/ (VENDOR CLAIM)
