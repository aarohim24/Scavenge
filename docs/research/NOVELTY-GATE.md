# Novelty Gate — Arm E and CrawlBench

Targeted prior-art falsification pass, run after CrawlBench v0.4. Research only; no
implementation code was written or modified. Date: 2026-08-17.

Evidence classes used throughout: **VERIFIED IN CODE**, **VERIFIED IN DOCUMENTATION**,
**RESEARCH PAPER**, **PATENT**, **VENDOR CLAIM**, **INFERENCE**, **UNVERIFIED**.

---

## 1. Verdict

**Arm E — NOVEL COMBINATION, COMPONENTS KNOWN.**

Every component of E is established prior art: multi-source extraction, conflict
detection between representations of the same value, provenance retention, and
cost-sensitive escalation from a cheap observation to an expensive one. No system or
paper was found that uses *within-document* disagreement between representation
channels as the trigger for *browser/rendering escalation*. The combination is what
remains, not any part.

**CrawlBench — NOVELTY PLAUSIBLE.**

No benchmark was found that jointly measures structured-extraction correctness,
separates confidently-wrong output from failed output, and reports browser work and
compute cost against declared adaptive-predictor history.

---

## 2. Candidate Contribution

Using disagreement between independent representation channels *inside a single cheap
document* as a pre-render sufficiency signal that decides whether browser execution is
required — and a benchmark that can measure whether that signal is worth its cost.

---

## 3. Closest Prior Art

**Google Merchant Center "automatic item updates"** — VERIFIED IN DOCUMENTATION
([support.google.com/merchants/answer/3246284](https://support.google.com/merchants/answer/3246284)).

Google crawls a product landing page, extracts its structured-data markup with
"advanced data extractors", compares the result against the price/availability in the
merchant's submitted feed, and acts automatically on the disagreement: "If your most
recent product upload contains a product that costs $4 USD, but your product landing
page lists it as $3 USD, we'll update the product to $3 USD in your ads or product
listings." The stated purpose is "to eliminate any mismatches in your product pricing,
availability, and condition."

This is conflict-aware verification of a structured field, deployed at web scale, and
it is the nearest deployed predecessor to E. It is not Crawlee, and it did not come
from the crawling literature.

| | Google automatic item updates | Arm E |
|---|---|---|
| Sources compared | Merchant feed vs landing-page markup | Two channels inside one document (DOM vs JSON-LD/embedded JSON) |
| Unit of comparison | Two artifacts produced at different times | One HTTP response |
| Action on conflict | Correct the value (pick the page) | Refuse to trust the cheap extraction; escalate |
| Purpose | Data freshness/accuracy for ads | Deciding whether to pay for rendering |
| Cost model | None published | The entire point |

**Overlap:** both treat disagreement between two representations of the same field as
evidence that one of them should not be trusted. **Difference:** Google resolves the
conflict by choosing a winner; E declines to choose and spends compute instead. Google's
comparison is cross-artifact and asynchronous; E's is within-document and synchronous,
which is what makes it usable *before* the expensive fetch.

---

## 4. What Is Definitely Not Novel

We must never claim any of these:

1. **Extracting from DOM plus JSON-LD/microdata/RDFa/embedded JSON** (idea A). `extruct`
   has done exactly this for years — VERIFIED IN DOCUMENTATION
   ([github.com/scrapinghub/extruct](https://github.com/scrapinghub/extruct)).
2. **Merging or choosing between conflicting values from multiple sources** (idea B).
   This is the data-fusion and truth-discovery literature; see Dong & Naumann, *Data
   Fusion: Resolving Conflicts from Multiple Sources* — RESEARCH PAPER
   ([arXiv:1503.00310](https://arxiv.org/abs/1503.00310)).
3. **Verifying an extraction from cheap signals without a reference run.** Kushmerick's
   RAPTURE, already reproduced as arm E0 — RESEARCH PAPER
   ([AAAI-99](https://cdn.aaai.org/AAAI/1999/AAAI99-011.pdf)).
4. **Using redundancy/agreement among extractions as a correctness probability.**
   Downey, Etzioni & Soderland's urns model — RESEARCH PAPER
   ([turing.cs.washington.edu/papers/urns_ijcai05.pdf](https://turing.cs.washington.edu/papers/urns_ijcai05.pdf)).
5. **Disagreement between two views as a learning/decision signal.** Co-training and the
   whole disagreement-based family — RESEARCH PAPER (Blum & Mitchell 1998; Zhou,
   *Theoretical Foundation of Co-Training and Disagreement-Based Algorithms*,
   [arXiv:1708.04403](https://arxiv.org/pdf/1708.04403)).
6. **The generic cascade**: cheap observation → uncertainty → expensive observation.
   Cascade classifiers, selective classification, sensor fusion, active acquisition.
   Ancient and universal. Claiming it would be embarrassing.
7. **Adaptive HTTP/browser execution.** Crawlee ships it — VERIFIED IN CODE
   (`AdaptivePlaywrightCrawler`, v1.9.2).
8. **Detecting that page markup disagrees with page content.** Google requires markup to
   be "a true representation of the page content" and treats violations as a manual-action
   offence — VERIFIED IN DOCUMENTATION
   ([sd-policies](https://developers.google.com/search/docs/appearance/structured-data/sd-policies)).

---

## 5. What May Still Be Novel/Differentiated

Precisely three things, in descending confidence:

1. **The escalation coupling (idea D).** No paper, repository, product doc, or patent was
   found in which within-document representation conflict decides whether to run a
   browser. Crawlee's `result_comparator` compares HTTP against browser output — it can
   only fire *after* paying for the browser (VERIFIED IN CODE, `_result_comparator.py`).
   E's signal is available before. That inversion is the differentiated part.
2. **Conflict as a reason to *withhold trust* rather than to *pick a winner*.** The fusion
   and truth-discovery literature is overwhelmingly about resolution. Declining to resolve,
   and converting the conflict into an acquisition decision, is a different use of the
   same observation.
3. **The measurement frame.** CrawlBench can express "confidently wrong" as a first-class
   outcome and price it against compute. Nothing found does that (see §12).

Not novel and not claimed: the conflict detector itself, the provenance record, the
normalization, and the cascade shape.

---

## 6. Academic Prior Art

Most relevant only.

- **Kushmerick, "Regression testing for wrapper maintenance", AAAI-99** — RESEARCH PAPER.
  RAPTURE: nine content features, normal densities, combined into a per-label verification
  probability. Idea **C**, single-representation. Already reproduced and measured as E0.
  [PDF](https://cdn.aaai.org/AAAI/1999/AAAI99-011.pdf)
- **Lerman, Minton & Knoblock, JAIR 18 (2003)** — RESEARCH PAPER. Pattern-based wrapper
  verification and reinduction; reports RAPTURE's reliance on HTML density. Idea **C**.
  [arXiv:1106.4872](https://arxiv.org/abs/1106.4872)
- **Downey, Etzioni & Soderland, urns model (IJCAI-05; AIJ 174, 2010)** — RESEARCH PAPER.
  Agreement/redundancy across *many documents* yields extraction confidence. Idea **C**,
  but the redundancy is corpus-level, not within-document. The closest academic ancestor
  of "agreement is evidence".
  [PDF](https://turing.cs.washington.edu/papers/urns_ijcai05.pdf)
- **Blum & Mitchell, co-training (COLT 1998); Nigam & Ghani (2000); Zhou (2017 survey)** —
  RESEARCH PAPER. The formal treatment of two-view independence and of disagreement as a
  signal, including proofs of what breaks when views are dependent. Directly governs §9.
  [arXiv:1708.04403](https://arxiv.org/pdf/1708.04403)
- **Dong & Naumann, "Data Fusion: Resolving Conflicts from Multiple Sources" (VLDB 2009 /
  survey)** — RESEARCH PAPER. Idea **B**: conflict resolution, source accuracy, copy
  detection. [arXiv:1503.00310](https://arxiv.org/abs/1503.00310)
- **Meusel & Paulheim, "Heuristics for Fixing Common Errors in Deployed schema.org
  Microdata" (ESWC 2015)** and *Towards More Accurate Statistical Profiling of Deployed
  schema.org Microdata* (JDIQ 2016) — RESEARCH PAPER. Establishes that deployed structured
  data is frequently wrong, at web scale. Relevant to §10 rather than to novelty.
  [Springer](https://link.springer.com/chapter/10.1007/978-3-319-18818-8_10) ·
  [ACM](https://dl.acm.org/doi/10.1145/2992788)

**Negative result worth recording:** searches for multi-view/cross-view consistency in
*web extraction* return computer-vision and multi-view clustering work, not extraction
validation. The IE sense of "views" (page text vs anchor text) belongs to co-training and
is used for classification, not for extraction-validity or acquisition decisions.

---

## 7. Open-Source Prior Art

- **`extruct`** (Zyte) — VERIFIED IN DOCUMENTATION. Extracts Microdata, JSON-LD, RDFa,
  Open Graph, Microformats from one page. Returns them side by side and does **not**
  compare, reconcile, or validate them. Idea **A** only. This is the single most important
  "already exists" check, and it stops at A.
  [github.com/scrapinghub/extruct](https://github.com/scrapinghub/extruct)
- **`web-meta-scraper`** — VERIFIED IN DOCUMENTATION. Extracts OG/JSON-LD/Twitter/meta and
  performs "priority-based merging that automatically resolves conflicts when the same
  field exists in multiple sources, with fully customizable resolve rules." Idea **B**.
  It detects the same conflicts E does and then *silently resolves them by precedence* —
  the opposite of treating the conflict as information.
  [github.com/cmg8431/web-meta-scraper](https://github.com/cmg8431/web-meta-scraper)
- **Crawlee `AdaptivePlaywrightCrawler`** — VERIFIED IN CODE (v1.9.2, pinned and read).
  `result_checker` gates the static path; `result_comparator` compares static against
  browser output during detection sampling. Idea **D**, but the comparison requires the
  browser to have already run. Also: supplying a checker silently replaces the comparator
  (`create_default_comparator`), which CrawlBench v0.2 measured.
- **Scrapy / Crawl4AI / Firecrawl / ScrapeGraphAI / trafilatura** — UNVERIFIED for
  conflict logic; no evidence found of cross-representation conflict detection. The common
  documented pattern is a *fallback cascade on absence* ("structured payloads first, static
  HTML second, browser third"), which triggers on missing data, not on contradiction.

**No open-source implementation of idea D was found.**

---

## 8. Commercial / Patent Prior Art

- **Google Merchant Center automatic item updates** — VERIFIED IN DOCUMENTATION. See §3.
  The strongest commercial prior art, and it is genuinely close on **C**.
- **Google Search structured-data policies** — VERIFIED IN DOCUMENTATION. "Your structured
  data must be a true representation of the page content"; mismatch can cause a manual
  action. The page does **not** document automated cross-checking of markup against
  rendered content. Widespread SEO-industry claims that "Google cross-references the schema
  price against the visible price" are **VENDOR CLAIM / UNVERIFIED** and are not treated as
  evidence here.
- **Zyte API** — VERIFIED IN DOCUMENTATION. `extractFrom` lets a caller choose
  `browserHtml` or `httpResponseBody` per extraction type. This is a *manual, static*
  choice, not conflict-driven escalation.
  [docs.zyte.com](https://docs.zyte.com/zyte-api/usage/extract/index.html)
- **Diffbot Analyze API** — VERIFIED IN DOCUMENTATION. Classifies page type and routes to
  the matching extraction API, with a `fallback` argument. Routing is by *page type*, not
  by extraction disagreement.
  [support.diffbot.com](https://support.diffbot.com/automatic-apis/the-analyze-api-fallback-argument)
- **Patents** — searched Google Patents around web-extraction verification and multi-source
  reconciliation. Nearest hits (US8954438B1 structured metadata extraction — cross-validates
  *across pages/languages*; US20100083095A1 — compares multiple *instances* of a page to
  separate template from data) are **PATENT** evidence for cross-*document* comparison, not
  within-document channel conflict driving execution. No blocking hit found. This is not a
  freedom-to-operate opinion.

---

## 9. Source-Independence Problem

**Our terminology is technically misleading and should change.**

E currently calls DOM, ATTRIBUTE, JSON_LD and EMBEDDED_JSON "independent sources". They are
almost never independent in the statistical sense. On most real sites all four are rendered
from the same backend object by the same template, so agreement is a single observation
reported four times, not four confirmations. Co-training theory is the established
treatment of exactly this: conditional independence of views is the assumption that makes
agreement informative, Nigam & Ghani showed it is routinely violated in practice, and
performance degrades when it is (RESEARCH PAPER, §6).

Two consequences we must accept:

1. **Agreement proves almost nothing.** E already never claims otherwise — it only acts on
   disagreement — and that asymmetry is now theoretically justified rather than lucky.
   Disagreement is informative under much weaker assumptions than agreement is.
2. **The right name is "representation channel", not "independent source".** The channels
   are distinct *renderings* of a value that may diverge through caching, template age, or
   pipeline skew. That is precisely why divergence is interesting, and it is not
   independence.

Recommendation: rename `EvidenceSource` → representation channel language, and drop the word
"independent" from documentation and comments. This is a naming/documentation change, not a
behaviour change, and it was not made in this pass because no implementation code may be
modified.

---

## 10. Real-World Conflict Semantics

This is the most dangerous section for E, and the evidence cuts against us.

DOM/JSON-LD price disagreement in the wild frequently does **not** mean the cheap extraction
is wrong:

- **Stale cached JSON-LD is a known, common failure mode.** Aggressively cached pages serve
  Product JSON-LD whose price no longer matches the live/visible price — VENDOR CLAIM
  (SEO practitioner literature), corroborated structurally by Google's own automatic item
  updates existing to repair exactly this class of mismatch (VERIFIED IN DOCUMENTATION).
  Here the *DOM* is right and the *JSON-LD* is stale — the reverse of our fixture.
- **Sale vs list price.** schema.org has no `salePrice`; the convention is to overwrite
  `price` and add `priceValidUntil`. Pages routinely display a struck-through list price and
  a sale price while the markup carries one of them — VERIFIED IN DOCUMENTATION
  ([schema.org/Offer](https://schema.org/Offer), Google Merchant Center guidance).
- **Multiple offers/variants.** A `Product` with an `offers` array legitimately carries many
  prices for one visible page.
- **Localization, currency, personalization, A/B tests, logged-in pricing.**
- **Deployed structured data is simply often wrong.** Meusel & Paulheim found errors at web
  scale in deployed schema.org markup — RESEARCH PAPER.

**Implication:** at scale, a rule of "any DOM/JSON-LD price disagreement ⇒ escalate" would
fire frequently, and in a large fraction of cases the cheap DOM value would have been
correct. Those are false rejects, and every false reject costs exactly the browser render E
exists to avoid. Our benchmark cannot see this: `conflicting-prices` is a synthetic fixture
in which disagreement *does* imply the DOM is stale. **We have one favourable data point and
a documented population of unfavourable ones.** This is the single strongest reason not to
believe E's v0.4 result generalizes.

---

## 11. E vs Prior Art (A/B/C/D)

| System | A multi-source | B fusion | C conflict-aware verification | D conflict-driven escalation |
|---|---|---|---|---|
| `extruct` | ✅ | — | — | — |
| `web-meta-scraper` | ✅ | ✅ | — | — |
| Dong & Naumann / truth discovery | ✅ | ✅ | partial | — |
| Downey urns | ✅ (cross-document) | — | ✅ | — |
| RAPTURE / E0 | — | — | ✅ (single representation) | — |
| Co-training family | ✅ (two views) | — | ✅ (disagreement as signal) | — |
| Google Merchant automatic item updates | ✅ (feed vs page) | ✅ (picks page) | ✅ | — |
| Crawlee D2 `result_comparator` | ✅ (HTTP vs browser) | — | ✅ | ⚠️ post-hoc only — needs the browser first |
| Zyte `extractFrom` / Diffbot Analyze | — | — | — | routing by type/config, not conflict |
| **Arm E** | ✅ | ✗ deliberately | ✅ within-document | ✅ **pre-render** |

A and B are thoroughly occupied. C is occupied by both research (RAPTURE, urns,
co-training) and production (Google). **D is the only column with no entry**, and Crawlee's
near-miss is instructive: it has the comparison but only after paying the cost that the
comparison was supposed to avoid.

---

## 12. CrawlBench Prior Art

Searched once more, specifically for benchmarks. Nothing was found that jointly measures
extraction correctness, separates confidently-wrong from failed, and reports browser work
and compute cost with declared predictor history.

What exists instead:
- **Vendor-run scraping benchmarks** (Bright Data, Zyte, Browserbase, Scrapfly comparisons)
  — VENDOR CLAIM. One industry write-up states plainly that "a genuinely neutral,
  cross-vendor performance benchmark for this category is hard to find, precisely because
  most players in it have an incentive to run their own." These measure success rate and
  latency, not correctness-vs-cost, and never separate confidently-wrong output.
- **Wrapper-maintenance evaluations** (Kushmerick's 27 sites; Lerman's 27 wrappers) —
  RESEARCH PAPER. Measure verification precision/recall, no compute accounting.
- **Extraction-quality studies** (Zyte's product data quality work) — VENDOR CLAIM.
  Correctness only.

**CrawlBench remains NOVELTY PLAUSIBLE**, and it is now the only asset in this project that
has survived four consecutive falsification attempts. It has also repeatedly produced
results that changed our plans — the comparator footgun, the corpus-composition effect on
predictor behaviour, E0's degeneracy — which is what a benchmark is for.

---

## 13. Strongest Argument Against Building E

The signal is one synthetic fixture wide, and the real world points the other way.

E's entire measured advantage is `conflicting-prices`, a fixture we authored, in which
disagreement was *constructed* to mean the DOM is stale. §10 documents that in production
the most common cause of DOM/JSON-LD price disagreement is **stale JSON-LD** — the opposite
polarity — plus sale/list pricing, variants, and localization, none of which imply the cheap
extraction is wrong. A production E would therefore escalate often and be wrong to escalate
often, paying the exact browser cost it was designed to save, while still missing the
majority of false successes (2 of 3 in our own corpus, both undetectable in principle from a
single document).

Worse, the failure it *does* catch is the one a schema-aware crawler can already handle more
cheaply: if DOM and JSON-LD disagree you could simply prefer the more reliable channel — as
Google does — without rendering anything. E spends a browser where a precedence rule might
do. And C is already occupied by a deployed system operating at a scale we cannot approach.

The honest summary: we have found a gap in the literature, but a gap is not a demand signal.
Recall from `CONFIRMATION-PASS.md` §6 that the Crawlee tracker contains **no** user
complaints about unnecessary browser execution cost.

## 14. Strongest Argument For Building E

The one column nobody occupies is the one that matters economically.

Every deployed conflict-aware system compares two representations *after* both exist —
Google after crawling, Crawlee after rendering. That ordering makes the signal useful for
data repair but useless for cost control. E's observation is that a meaningful fraction of
"the cheap answer is untrustworthy" is decidable from bytes you have *already paid for*,
before the expensive step. If that holds even weakly at scale, it converts a data-quality
technique into a scheduling technique, which is a different economic object.

The supporting evidence is not nothing: CrawlBench v0.2 measured that Crawlee's own naive
checker accepts stale-but-complete records and that its default wiring then trains the
predictor to skip the browser exactly where it was needed — a real, reproduced, upstream
defect. E addresses precisely that failure with information already in hand. And E's
asymmetry is theoretically sound: it acts only on disagreement, which per co-training theory
survives the loss of view independence far better than agreement does.

Finally, the cost of the next falsification step is very low, and it is the *last* cheap
question standing between us and a defensible answer.

## 15. Final Recommendation

**CONTINUE E EXPERIMENTS** — with one experiment, a pre-declared kill criterion, and no
implementation work beyond it.

This is a narrow endorsement. CrawlBench is the stronger *asset* and should remain the
project's centre of gravity; E is worth exactly one more measurement because the measurement
is cheap and decisive. If it fails, we stop, and CrawlBench keeps its value.

## 16. Next Experiment

**Measure the prevalence and precision of within-document price disagreement on real
e-commerce pages.**

On a fixed, declared sample of real product pages (public web, first use in this project):
for every page where DOM and JSON-LD/embedded-JSON both yield a price, record whether they
disagree; then render each disagreeing page and record whether the rendered price matches
the DOM value, the structured-data value, or neither.

Two numbers come out: **prevalence** (how often disagreement fires) and **precision** (given
disagreement, how often the cheap DOM value was actually wrong — i.e. how often escalation
was justified).

Pre-declared kill criterion, fixed before the run: **if precision is below 0.5 — meaning
disagreement more often than not indicates stale markup rather than a wrong cheap
extraction — E is dead as an escalation signal and we stop.** A precedence rule would then be
strictly better than rendering, and §10's argument wins.

This experiment cannot be run on local fixtures, because the question is entirely about
whether real-world conflict semantics match our synthetic assumption. It requires no new
extraction machinery, no historical learning, no LLM, and no Crawlee integration.
