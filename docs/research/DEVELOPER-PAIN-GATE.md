# Developer-Pain Gate

A demand investigation run deliberately against our own direction. No implementation
code was written or modified. Evidence classes: **PRIMARY SOURCE** (developer speaking
in their own words, or official project documentation), **COMMUNITY ANECDOTE**,
**VENDOR CLAIM**, **ENGINEERING INFERENCE**.

---

## 1. Executive Verdict

**PIVOT — DIAGNOSTIC TOOL.**

Three findings drive this, and two of them hurt us:

1. **The name is already taken by the closest competitor.** Firecrawl publishes a
   benchmark called **CrawlBench** — LLM structured-extraction accuracy over ~2,300
   labelled datapoints — and has open-sourced a second benchmark, Scrape-Evals, over
   ~1,000 real URLs. Structured-extraction-correctness benchmarking is now occupied by
   a funded vendor with distribution and better data than ours.
   ([Firecrawl CrawlBench](https://www.firecrawl.dev/blog/crawlbench-llm-extraction),
   VENDOR CLAIM but self-describing and verifiable.)
2. **The cost axis is still unoccupied.** Firecrawl's CrawlBench explicitly does *not*
   measure compute cost, browser usage, or HTTP-versus-browser execution. That is
   precisely the axis our benchmark measures. Our differentiation survives — but it has
   narrowed from "correctness benchmark" to "correctness *per unit of compute*".
3. **The strongest developer pain our work touches is not benchmarking — it is
   per-target diagnosis.** Scrapy's own documentation prescribes a manual workflow
   (network tab → find the JSON request → reproduce it → headless browser only if that
   fails) and concedes it "may not seem efficient in developer time". That is a
   recurring, documented, manual task that developers perform per site, and it is what
   our instrument already half-implements.

A benchmark earns stars. A diagnostic CLI earns installs. The evidence supports the
latter, and the benchmark should survive as the thing that *validates* the diagnostic's
claims rather than as the product.

---

## 2. Research Method

Hacker News was searched through the Algolia API, pulling whole comment trees rather
than search snippets, because snippet search proved too noisy to be evidence. GitHub
was searched through its issues API sorted by reactions, so severity came from reading
issues rather than counting them. Official project documentation was read directly.
Reddit's JSON API returned HTTP 403 to scripted access, so Reddit appears here only via
search engines and is weighted as anecdote — a real gap in this study.

Deliberate discipline: multiple comments in one thread count as one signal; issue counts
were not treated as severity; SEO and vendor marketing were classified as such; and I
searched specifically for evidence against our direction, which is how findings 1 and 3
above were found.

---

## 3. Developer Pain Ranking

Scores are 1–5. **Existing solution: 1 = poorly solved, 5 = already solved well**, so a
high score there argues *against* building.

| Pain | Freq | Sev | Existing soln | Adoption opp | Fit with us |
|---|---|---|---|---|---|
| Scraper breakage / maintenance when sites change | 5 | 4 | 2 | 4 | 2 |
| Silent wrong data (200 OK, plausible-but-wrong) | 4 | 5 | 2 | 4 | **5** |
| Per-target diagnosis: do I need a browser? is there an API? | 4 | 3 | 2 | **4** | **5** |
| Anti-bot / proxies / CAPTCHA | 5 | 5 | 3 | 2 | 1 |
| Browser CPU/RAM cost at scale | 2 | 5 | 3 | 3 | **4** |
| Choosing between tools / trusting benchmarks | 3 | 2 | 2 | 3 | **4** |
| Browser memory leaks, long-run stability | 3 | 4 | 3 | 2 | 1 |

Anti-bot scores highest on raw frequency and severity and is the single biggest pain in
this field — and it is the one we have explicitly refused to work on, correctly. It is
an arms race with poor incentives, and nothing in our work addresses it. That is the
honest headline: **the biggest pain in scraping is not our pain.**

---

## 4. Hacker News Evidence

From *Show HN: Lightpanda* ([42817439](https://news.ycombinator.com/item?id=42817439),
319 points, 137 comments) — all PRIMARY SOURCE:

- **fbouvier** (founder): "We've worked a lot with Chrome headless at our previous
  company, **scraping millions of web pages per day**. While it's powerful, it's also
  **heavy on CPU and memory usage**." And later: "we were scraping >20 millions of
  webpages per day, with **thousands of instances of Chrome headless in parallel**."
- **katiehallett** (co-founder): "we **spent a ton of $ on scraping infrastructure**
  spinning up headless Chrome instances." — a company was founded on this cost.
- **JoelEinbinder** (Playwright maintainer) — **the strongest evidence against us**:
  "When I've talked to people running this kind of ai scraping/agent workflow, **the
  costs of the AI parts dwarf that of the web browser parts. This causes computational
  cost of the browser to become irrelevant.** I'm curious what situation you got
  yourself in where optimizing the browser results in meaningful savings."
- **JoelEinbinder**, on benchmark quality: "I think your ram usage benchmark is
  deceptive… **if the benchmark ran on a random set of real websites**, ram usage would
  not be meaningfully lower than Chrome." — a maintainer demanding realistic corpora,
  which is an argument *for* rigorous benchmarking.

From *Ask HN: What are best tools for web scraping?*
([15694118](https://news.ycombinator.com/item?id=15694118), 502 points, 215 comments):

- **sharmi**: Scrapy's "only drawback is handling pure javascript sites. **We have to
  manually dig into the api** or add a headless browser invocation within the scrapy
  handler."
- **doh**: "if you're crawling big platforms, there are often ways in that can scale and
  be undetected for very long periods of time. Those include **forgotten API
  endpoints**."

*Ask HN: Web scraping in production?*
([43977349](https://news.ycombinator.com/item?id=43977349)) drew only 6 comments and
almost no substantive replies — a negative signal I am recording rather than omitting:
the question we care most about did not generate discussion.

---

## 5. Reddit Evidence

**Methodological failure, disclosed:** Reddit's JSON endpoints returned HTTP 403 to
scripted access, so I could not sample r/webscraping systematically. Search-engine
summaries repeat that maintenance and breakage dominate, but I will not present
second-hand summaries of Reddit as evidence. **This is a genuine gap in the study**, and
any future demand work should cover it properly with an authenticated client.

---

## 6. GitHub Issue / Discussion Evidence

Read rather than counted. The notable result is **how weak the signal is**:

- Browser memory is a genuine long-running pain: puppeteer
  [#4059](https://github.com/puppeteer/puppeteer/issues/4059) (`page.evaluate()` leaking
  memory), [#9283](https://github.com/puppeteer/puppeteer/issues/9283),
  [#5893](https://github.com/puppeteer/puppeteer/issues/5893); Crawlee
  [discussion #2308](https://github.com/apify/crawlee/discussions/2308) asks for
  automatic memory management. PRIMARY SOURCE.
- Scrapy [#6597](https://github.com/scrapy/scrapy/issues/6597) "sane defaults that do no
  harm" — 16 reactions, open, the highest-reaction relevant issue I found.
- Crawlee-Python: 91 issues match rendering/adaptive/memory, but the **top-reacted has 5
  reactions**. There is no groundswell demanding better adaptive rendering.
- Crawl4AI "[Bug]: Incomplete Extraction"
  ([#505](https://github.com/unclecode/crawl4ai/issues/505)) and malformed-table issues
  exist but with ~0–2 reactions each.

**ENGINEERING INFERENCE:** the problems we chose are real but nobody is filing angry,
highly-upvoted issues about them. Compare anti-bot, where entire businesses exist. Low
reaction counts are weak evidence of low urgency.

---

## 7. Engineering-Blog Evidence

Weakest category, and I am discounting it heavily. The "scrapers fail silently" theme is
abundant — "a scraper may return a 200 OK status, the job finishes on schedule, and the
dashboard stays green, but the data flowing into your systems is incomplete, stale, or
simply wrong" — but nearly every such article is **content marketing by a scraping
vendor** (Ficstar, webscraper.io, Firecrawl glossary, Medium reposts). VENDOR CLAIM.

That is an uncomfortable finding for us: the concept our benchmark is built around
(`FALSE_SUCCESS`) is validated far more strongly in *marketing* than in developer
forums. Vendors write about it because it sells monitoring; that is not the same as
developers demanding a fix.

---

## 8. Repeated Workarounds

Workarounds are the best evidence of missing infrastructure, and these recur:

1. **Open DevTools, find the XHR/JSON endpoint, call it directly.** Prescribed by
   [Scrapy's official documentation](https://docs.scrapy.org/en/latest/topics/dynamic-content.html)
   (PRIMARY SOURCE), repeated by HN commenters, and the subject of a large tutorial
   genre. Someone has already automated a slice of it
   ([api_hunter_cli](https://github.com/engcarlosperezmolero/api_hunter_cli)).
2. **Try HTTP first, escalate to a browser only if it fails.** Scrapy's documented
   fallback order; Crawlee automates a version of it.
3. **Restart Chromium every N pages** to survive leaks (Crawlee's
   `retire_browser_after_page_count`, and the puppeteer issues above).
4. **View-source vs rendered-DOM comparison** to decide if JS is required — now sold as
   free "JavaScript Rendering Checker" tools.
5. **Hand-written per-site validation rules** to catch bad data downstream.

Workarounds 1, 2 and 4 are all the *same underlying task*: figuring out what a specific
target actually requires. That is the clearest missing-tool signal in this study.

---

## 9. Evidence of Actual Cost

Separating the categories as instructed:

- **MEASURED COST / PAID SOLUTION:** Lightpanda's founders ran "thousands of instances
  of Chrome headless in parallel" for 20M+ pages/day and "spent a ton of $" on it —
  enough to fund building a browser from scratch in Zig. PRIMARY SOURCE.
- **PAID SOLUTION:** an entire commercial tier exists — Browserless, Zyte, Bright Data,
  Firecrawl, ScrapingBee, Apify — which is proof of willingness to pay, though mostly
  for *anti-bot and infrastructure*, not for execution-mode optimisation.
- **COMPLAINT only:** browser RAM/CPU in the puppeteer/Crawlee issues.
- **COUNTER-EVIDENCE:** a Playwright maintainer states browser compute is "irrelevant"
  next to LLM inference costs for AI workloads. If the growth workload is AI-driven
  extraction, our cost axis shrinks exactly where the market is expanding.

---

## 10. HTTP-vs-Browser Decision Pain

The most directly relevant question, answered from primary sources.

[Scrapy's documentation](https://docs.scrapy.org/en/latest/topics/dynamic-content.html)
prescribes: find the data source in the network tool → inspect page source for embedded
JavaScript data → reproduce the request → extract → "fall back to headless browser" only
if reproducing proves impractical. It concedes: **"reproducing all necessary requests
may not seem efficient in developer time."**

So the decision is: **mostly manual, per-target, performed by hand in DevTools,
officially documented as the correct practice, and acknowledged by the framework itself
to cost developer time.** It is not considered trivial, and it is not well automated.

Partial existing solutions: Crawlee's `AdaptivePlaywrightCrawler` (automates the
*runtime* decision, not the *developer's* understanding, and our own v0.2 work measured
its miscalibration); JS-rendering checker web tools; `api_hunter_cli`. None gives a
developer a single evidence-backed answer for a specific target.

**This is the pain our existing instrument is closest to solving.**

---

## 11. False-Success / Silent-Corruption Pain

Developers do suffer this — "returning partial data that looks almost right, or scraping
the wrong element entirely", crawlers running "for weeks after a target site redesigns,
silently extracting stale data". But as noted in §7, the loudest sources are vendors.

Honest assessment: `FAILED` vs `FALSE_SUCCESS` is a **correct and useful distinction**
that practitioners clearly recognise once named, but I found **no evidence that
developers are searching for a benchmark that measures it**. They want *alerting* on
their own pipelines, which is a monitoring product, not a benchmark. This weakens our
benchmark positioning more than I expected going in.

---

## 12. Benchmark Demand

Demand for *trustworthy* comparison is real, and the incumbents' own critique is blunt:
"When a web scraping vendor publishes a benchmark, they control which URLs get tested,
how success is defined, how retries are handled… A 99% from one vendor and a 98% from
another describe two different tests, not two products." Even nominally independent
benchmarks turn out to be vendor-affiliated (Scrapeway → Scrapfly; ScrapingTest →
Scrape.do). ([String AI](https://www.usestring.ai/blog/web-scraping-benchmark-problem),
VENDOR CLAIM — and they are launching their own benchmark, which proves the point.)

But the space is **crowded and consolidating**: Firecrawl's CrawlBench and Scrape-Evals,
fastCRW, spider.cloud, webscraping.cc, plus academic work
([arXiv:2601.06301](https://arxiv.org/pdf/2601.06301) on LLM-powered scraping
benchmarks). Firecrawl's Scrape-Evals ships a HuggingFace dataset of ~1,000 real URLs.

**Verdict on benchmark demand: real but contested, and our specific slot — correctness
per unit of compute, with confidently-wrong counted separately — is the only part not
already occupied.**

---

## 13. Tool-Selection / Site-Diagnosis Pain

The instruction to separate these was correct, and the evidence separates cleanly.
"Which framework should I use?" is asked once per developer and answered adequately by
existing comparisons. **"How should I scrape *this site*?" is asked once per target**,
repeatedly, forever, and is answered today by opening DevTools by hand.

Site diagnosis is the higher-frequency, better-fitting pain. It is also the one where a
CLI has a plausible install story: you run it when you meet a new target, and it either
saves you fifteen minutes of DevTools work or it doesn't.

---

## 14. Problems Already Solved — DO NOT BUILD

Verified as adequately served; building here would be waste:

- **Browser automation** — Playwright/Puppeteer. Solved.
- **HTTP crawling, scheduling, retries, concurrency, browser pooling** — Scrapy, Crawlee.
  Solved; Crawlee's pool defaults are sane (verified in source during v0.2).
- **CSS/XPath extraction, Markdown conversion** — parsel, selectolax, trafilatura,
  Crawl4AI. Solved.
- **Multi-format structured-data extraction** — `extruct` reads JSON-LD, Microdata,
  RDFa, OpenGraph. Solved (verified in the novelty gate).
- **LLM-based extraction** — Crawl4AI, Firecrawl, ScrapeGraphAI. Crowded.
- **Proxy rotation / anti-bot** — a whole commercial industry. Do not enter.
- **Content-recall benchmarking** — Firecrawl Scrape-Evals now occupies this.
- **Adaptive HTTP/browser execution as a runtime feature** — Crawlee ships it.

---

## 15. Top Opportunities

Only three survive; the other candidates are eliminated in §14.

### Opportunity 1 — Per-target diagnostic ("what does this site actually need?")

- **Pain:** deciding execution strategy and finding the real data source for a new target.
- **Evidence:** Scrapy docs prescribing the manual workflow and conceding its developer-time
  cost (PRIMARY); sharmi and doh on HN (PRIMARY); a tutorial genre; `api_hunter_cli`.
- **Workaround:** DevTools by hand, per site.
- **Why existing tools miss it:** Crawlee automates the runtime decision but tells the
  developer nothing; JS-rendering checkers answer one bit; `api_hunter_cli` finds endpoints
  but does not compare representations or judge correctness.
- **Project:** a CLI that reports, for one URL: what the raw HTML already contains, what
  structured data exists, whether JS changes the fields you care about, whether an XHR/JSON
  endpoint serves the same data, and where the representations disagree.
- **Why OSS matters:** it inspects targets you may not want to send to a third-party API.
- **Adoption path:** single command, no infrastructure, useful on first run.
- **Biggest reason not to build:** the task may be *annoying but cheap* — fifteen minutes
  once per site — and developers may simply not install a tool for it.

### Opportunity 2 — Correctness-per-compute benchmark

- **Pain:** untrustworthy vendor benchmarks; no cost axis anywhere.
- **Evidence:** the benchmark-problem critique (VENDOR CLAIM); Firecrawl's benchmark
  explicitly omitting compute; a Playwright maintainer demanding realistic corpora (PRIMARY).
- **Why existing tools miss it:** every existing benchmark measures success or content
  recall, none measures resource cost per correct record, none separates confidently-wrong.
- **Biggest reason not to build:** benchmarks earn stars, not installs, and Firecrawl now
  owns the category name and the datasets.

### Opportunity 3 — Silent-corruption detection for running pipelines

- **Pain:** green dashboards over corrupt data.
- **Evidence:** abundant but overwhelmingly VENDOR CLAIM.
- **Biggest reason not to build:** it is a monitoring product requiring per-user
  integration and trust; ScrapeOps and others already occupy it; and the evidence base is
  marketing, not developer demand.

**Eliminated:** anti-bot (wrong fight), memory management (upstream's job), self-healing
selectors (crowded, and we have no advantage), LLM extraction (crowded).

---

## 16. Fit With Our Existing Work

What we have built, honestly mapped:

| Asset | Serves |
|---|---|
| Channel extraction with provenance (DOM/JSON-LD, candidates, paths) | **Diagnostic** — this is the diagnostic's core |
| Currency-aware money parsing, ambiguity refusal | **Diagnostic** and benchmark |
| HTTP vs warm-browser measurement, CPU accounting | **Benchmark**; diagnostic's "is a browser needed" answer |
| `CORRECT`/`FALSE_SUCCESS`/`FAILED` with independent ground truth | **Benchmark** |
| Crawlee adaptive integration, predictor-history and ordering effects | Benchmark only; narrow audience |
| RAPTURE baseline (E0), naive checker, comparator baselines | Research validation only |
| Arm E representation-channel disagreement | **Diagnostic** — "these two sources disagree, look here" |
| Sampling methodology, polite collection | Both |

The uncomfortable observation: **the components with the best product fit are the
instrument, not the arms.** Arm E as an *escalation policy* has weak demand evidence.
Arm E as a *diagnostic finding shown to a human* — "your cheap HTML says 2999, the
rendered page says 1999" — needs no precision threshold at all, because a human
adjudicates. The same machinery is worth more when it advises than when it decides.

---

## 17. Benchmark vs Diagnostic vs Runtime

- **A — Benchmark:** strongest intellectual asset, weakest adoption. It has repeatedly
  killed our own bad ideas, which is exactly what it is for. Keep it; do not lead with it.
- **B — Diagnostic:** best match to a documented, repeated, manual developer task; lowest
  trust barrier; directly reuses what we built. **Recommended.**
- **C — Runtime:** highest trust barrier, occupied by Crawlee, and our own measurements
  found the signal it would depend on to be one fixture wide. Not justified.
- **D/E:** no evidence for a different pain we are positioned to serve, and not enough
  reason to stop entirely.

---

## 18. Firecrawl Test

*Why would someone use this instead of Firecrawl?*

For a runtime or an extraction API: **no credible answer today.** Firecrawl is faster to
adopt, hosted, handles anti-bot, and now publishes its own benchmarks.

The only defensible answers are diagnostic-shaped, and both are pre-purchase rather than
competitive: *"this tells you whether you need Firecrawl or a browser at all for this
target, before you pay per page"*, and *"this runs locally against targets you cannot
send to a third-party API"*. Note that both make us **complementary to Firecrawl, not a
replacement** — which is a more honest and more defensible position than competing.

A cost claim ("same correctness, 60% less browser CPU") is currently unsupported. We have
no such measurement on real sites, and our attempt to get one is still blocked at the
sampling frame.

## 19. Crawlee Test

*Why wouldn't this be a Crawlee plugin?*

For the **runtime** form, it should be — and if the cross-representation signal ever
proves out, the honest home is a `result_checker`/`result_comparator` contribution plus
an upstream issue about the `create_default_comparator` footgun we verified and measured
in v0.2. That contribution is worth making regardless of what else we build.

For the **diagnostic** form, it should not: it is a developer-facing CLI for
understanding a target before writing any crawler, which is outside Crawlee's scope and
not tied to its runtime.

## 20. Benchmark Test

*Would crawler maintainers actually run it?* **Probably not, on current evidence.** I
found no maintainer asking for third-party regression infrastructure; projects run their
own suites. The one genuine maintainer-side signal is Playwright's Joel Einbinder
challenging a competitor's benchmark as unrealistic — which shows maintainers care about
benchmark *rigour* when their project is being compared, not that they want to adopt
someone else's harness. A benchmark that only produces a leaderboard has weak adoption
potential, and we should assume ours would be used mainly by us.

---

## 21. Strongest Argument Against Continuing

The biggest pains in scraping — anti-bot, proxies, breakage — are ones we have
deliberately refused to work on. The pain we chose, browser compute, is dismissed as
"irrelevant" by a Playwright maintainer for the fastest-growing workload class, and is
acute only for a handful of firms at 20M pages/day who solve it by building their own
browser. The concept we built the benchmark around, false success, is evidenced mostly
by vendor marketing. Our benchmark's category name is already taken by a better-funded
competitor with better datasets. GitHub reaction counts across every relevant project are
in the single digits. And after four increments, our candidate mechanism rests on one
synthetic fixture and a real-world validation we have not been able to run.

A fair reading: we have built excellent measurement apparatus for a problem the market
has not asked us to solve.

## 22. Strongest Argument For Continuing

One documented, repeated, manual developer task remains unautomated: figuring out what a
specific target actually requires. Scrapy's own documentation describes the workflow and
concedes it costs developer time; HN practitioners describe doing it by hand; a tutorial
genre exists precisely because the answer must be re-derived per site; and the partial
tools that exist each answer one fragment. We have already built the components that
answer it with evidence rather than guesswork — channel extraction with provenance,
locale-correct parsing, cheap-versus-rendered comparison, and honest ambiguity reporting
— and we built them to a standard of rigour that most tools in this space visibly lack.

And the discipline itself has value: this project has now killed a stale-price heuristic,
a RAPTURE reproduction, and its own novelty claim, on evidence. That is a rare asset.

---

## 23. Final Verdict

**PIVOT — DIAGNOSTIC TOOL.**

Lead with a per-target diagnostic CLI. Keep the benchmark as internal validation
infrastructure — it is what makes the diagnostic's claims trustworthy — but stop treating
it as the product. Do not build a runtime. Contribute the Crawlee comparator finding
upstream regardless.

**Naming is now urgent, not cosmetic:** `CrawlBench` is Firecrawl's published benchmark
name. Continuing to use it internally risks a direct collision with the nearest
competitor. `RenderThrift` describes a cost thesis we have not proven; if the project
becomes a diagnostic, the name should describe **diagnosis**, not rendering efficiency.
New candidates worth checking: `sitesense`, `probeweb`, `whatsinthepage`, `pagerecon`,
`fetchdoctor`. I have not run registry checks on these; that is cheap and can wait until
the form is confirmed.

## 24. One Recommended Next Step

**Build a throwaway diagnostic prototype and test it on ten targets you did not choose.**

For a single URL, emit one evidence report: what the raw HTML contains, what structured
data exists, which fields change under rendering, whether an XHR/JSON endpoint serves the
same data, and where representations disagree. Then answer one question honestly: *did it
tell me something I would otherwise have spent DevTools time discovering?*

If it does not beat fifteen minutes in DevTools, that kills the diagnostic direction as
decisively as the previous gates killed the others — and the benchmark still stands.

---

## 25. Primary Sources

- Scrapy, *Selecting dynamically-loaded content* — https://docs.scrapy.org/en/latest/topics/dynamic-content.html (PRIMARY)
- HN, *Show HN: Lightpanda* — https://news.ycombinator.com/item?id=42817439 (PRIMARY)
- HN, *Ask HN: What are best tools for web scraping?* — https://news.ycombinator.com/item?id=15694118 (PRIMARY)
- HN, *Ask HN: Web scraping in production?* — https://news.ycombinator.com/item?id=43977349 (PRIMARY; notably low engagement)
- puppeteer#4059 — https://github.com/puppeteer/puppeteer/issues/4059 (PRIMARY)
- puppeteer#9283 — https://github.com/puppeteer/puppeteer/issues/9283 (PRIMARY)
- crawlee#2308 — https://github.com/apify/crawlee/discussions/2308 (PRIMARY)
- scrapy#6597 — https://github.com/scrapy/scrapy/issues/6597 (PRIMARY)
- crawl4ai#505 — https://github.com/unclecode/crawl4ai/issues/505 (PRIMARY)
- api_hunter_cli — https://github.com/engcarlosperezmolero/api_hunter_cli (PRIMARY)
- Firecrawl, *Evaluating Web Data Extraction with CrawlBench* — https://www.firecrawl.dev/blog/crawlbench-llm-extraction (VENDOR CLAIM)
- Firecrawl, *Introducing Scrape-Evals* — https://www.firecrawl.dev/blog/introducing-scrape-evals (VENDOR CLAIM)
- String AI, *The web scraping industry has a benchmark problem* — https://www.usestring.ai/blog/web-scraping-benchmark-problem (VENDOR CLAIM)
- *Beyond BeautifulSoup: Benchmarking LLM-Powered Web Scraping* — https://arxiv.org/pdf/2601.06301 (RESEARCH)
