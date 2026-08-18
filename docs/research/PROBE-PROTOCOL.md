# `probe` Prototype Protocol

Frozen before any real target was fetched. Nothing in this file may change once the
ten-target run begins. `probe` is a throwaway experiment, not a product; the existing
benchmark and the paused Arm E sampling work are untouched by it.

Codename `probe` is internal and temporary (`DIAGNOSTIC-NOVELTY-GATE.md` §7.6). No
registry claim, no branding.

## 1. Frozen scope

One command:

```
python -m probe inspect <url> [--field price] [--json]
```

It performs, in order:

1. `robots.txt` for our user agent. Disallowed → refuse and exit. No exceptions.
2. One polite HTTP GET (reusing the existing `PoliteFetcher`): status, content type, size.
3. Representations found in the **raw** body: visible DOM price elements, JSON-LD,
   embedded JSON blobs (`__NEXT_DATA__` and equivalents).
4. One warm-Playwright navigation of the same URL, capturing JSON-bodied `fetch`/`XHR`
   responses, then the same representation pass over the **rendered** DOM.
5. Deterministic correlation of the requested field's *value* across those channels.
6. A deterministic recommendation with the evidence that produced it.

Out of scope, permanently: crawling, scheduling, sessions, proxies, anti-bot, CAPTCHA,
dataset storage, an API, workers, a config system, a plugin layer, any LLM or embedding.

## 2. Field scope

`price` only, by default and in the ten-target run. Money normalisation reuses the
repaired currency-aware parser, including its refusal to guess ambiguous separators.
A second field type is out of scope for the experiment; adding one would be feature
work, not evidence.

## 3. Network observation limits

- Only responses whose content type is JSON, or whose body parses as JSON.
- Body read capped at 512 KB; larger bodies are recorded as observed-but-unread.
- At most 40 JSON responses recorded; overflow is reported explicitly, never truncated
  silently.
- No request is replayed. No authenticated request is reissued. Nothing is executed.
- Requests to `file:`, `localhost`, loopback, link-local or private address ranges are
  refused before navigation (SSRF discipline; the target URL is checked too).

## 4. Recommendation vocabulary (frozen)

Exactly these, and each must print the evidence lines that caused it:

```
HTTP MAY BE SUFFICIENT
STRUCTURED METADATA MAY BE SUFFICIENT
DIRECT JSON ENDPOINT WORTH INVESTIGATING
BROWSER RENDERING APPEARS NECESSARY
RESULT AMBIGUOUS — MANUAL INSPECTION RECOMMENDED
```

Advisory language only: LIKELY / APPEARS / FOUND / CHANGED / DISAGREES / NOT OBSERVED.
Never GUARANTEED / SAFE / CORRECT / ALWAYS. The tool must be able to say it cannot
determine a strategy, and that outcome is a success, not a failure.

## 5. Determinism requirement

Same page bytes in, same report out. The report is the differentiator precisely because
an LLM-mediated answer is not reproducible (`DIAGNOSTIC-NOVELTY-GATE.md` §6). Fixture
tests assert byte-stable reports.

## 6. Target selection procedure (declared before any target was drawn)

**Frame.** The Tranco top-domain list, an externally authored ranking we do not control,
**restricted to the top 10,000 ranks**. The depth was pinned before any domain was drawn:
drawing uniformly from the full million would return mostly parked and infrastructure
domains, which would test nothing. The restriction is by rank only and is blind to page
behaviour. The list ID in use is recorded in the results document. If Tranco is unreachable at run
time, the declared fallback — fixed now, not chosen later — is the Cloudflare Radar top
domains list.

**Mechanical filters, applied in this order, all blind to page behaviour:**

1. Domain resolves and its homepage returns HTTP 200 to a plain GET.
2. `robots.txt` permits our user agent on the homepage.
3. Target URL = the **first** same-host link in homepage document order whose path has
   at least two non-empty segments, and which robots permits.

**Draw.** Seeded random sample of domains from the frame (`seed = 20260818`), taken in
draw order until ten targets qualify. Every rejected domain is recorded with its reason.

**Forbidden as selection inputs:** presence of JSON-LD, presence of an API, whether the
page is client-rendered, whether representations disagree, and whether extraction
succeeds. None of these may be consulted before a target is committed.

The tool is expected to be unable to help on some of these. That is the point of not
choosing them.

## 7. Baseline procedure

For each target, in this order, and never the reverse:

1. **Unaided investigation first.** Read the raw body, search it by hand, inspect a raw
   network log, and reach a diagnosis without running `probe`. Timed.
2. **Then `probe`.** Timed.

Running the tool first would contaminate the baseline, so the order is fixed.

**Disclosed limitation:** this session cannot literally open Chrome DevTools. The
baseline is an *unaided investigation* — the same information DevTools shows (view
source, network log, structured data), gathered by hand — and it is reported as an
approximation of the DevTools workflow, not as the workflow itself. It is not optimised
to make the tool look good or bad.

**Second baseline, recorded per `DIAGNOSTIC-NOVELTY-GATE.md` §6:** whether an LLM agent
holding `chrome-devtools-mcp` would plausibly reach the same answer. Recorded as a
judgement, labelled as such, not as a measurement.

## 8. Recorded per target

```
diagnostic time · unaided time · diagnostic conclusion · unaided conclusion
useful finding unique to the diagnostic · important finding the diagnostic missed
misleading advice (yes/no, with what was wrong)
```

## 9. Kill criteria (predeclared, before any target was drawn)

Any one of these fires and the diagnostic direction dies:

1. **No meaningful time saving.** On at least 6 of 10 targets where unaided diagnosis
   took more than 5 minutes, `probe` saved less than 25% of that time. Targets that were
   trivial unaided (under 2 minutes) are excluded from this count rather than counted in
   our favour — a tool cannot beat a task that costs nothing.
2. **Misleading advice.** On 2 or more of 10 targets, `probe` recommends a cheaper
   strategy that unaided inspection shows does not actually carry the field.
3. **Mostly noise.** On 5 or more targets, reaching the conclusion requires reading more
   than roughly 60 lines of report, or requires opening the raw network/DOM dump anyway.
4. **Existing tool equivalent.** Implementation or testing shows an existing tool already
   provides essentially this experience.

## 10. Continue criteria

Continue only if `probe` repeatedly does at least one of: finds a useful JSON endpoint
automatically; establishes that raw HTTP suffices; shows a meaningful raw-vs-rendered
change in the field; surfaces a representation disagreement worth inspecting; or
correctly establishes that rendering is required — and does so faster or more clearly
than the unaided investigation.

"The tool detected many things" is not a result. "The tool told me what I needed to know
before I had to find it myself" is.

## 11. Mid-run defect policy

Inherited unchanged from `PILOT-PROTOCOL.md` A5. If a target exposes a defect,
measurement stops, affected observations are invalidated, the defect is fixed with a
regression test, the change is disclosed, and the affected targets restart cleanly.
Nothing is patched while results continue to accumulate.

---

## 12. Halt notice — frame/field mismatch (recorded 2026-08-18, before any target was probed)

The ten-target draw completed as declared and is recorded in `results/probe/targets.json`.
Selection was blind and is not in question. The targets are:

```
www.cwi.nl/en/login/                                    login form
www.registry.google/announcements/launch-details-…/     announcement
rexify.com.ng/user/login                                login form
languagetool.org/editor/new                             web editor
www.justice.gov/agencies/chart/grid                     org chart
www.123rf.com/stock-photo/independence_day.html         stock-photo search
www.bild.de/video/mediathek/video/…                     video page
ollama.com/library/glm-5.2                              model page
www.elcorreo.com/planes/playas/                         article
gravatar.com/site/signup                                signup form
```

**The defect is mine, and it is in this protocol, not in the tool.** §2 freezes a
single field — `price` — while §6 freezes a frame that is blind to what a page is
about. Those two decisions do not compose: at most one or two of these pages have a
price at all. Running the experiment as written would produce eight reports saying
`NO_VALUE_ANYWHERE → RESULT AMBIGUOUS`, which measures the mismatch I introduced, not
whether the diagnostic saves developer time.

Per §11, measurement is **halted before the first target was probed**. No target has
been fetched by `probe`. The draw, the seed, and the dispositions stand and are not
re-run. Resolving this requires a decision about scope, not a code change, and the
decision is recorded here before any target is inspected so that it cannot be mistaken
for a post-hoc adjustment.

## 13. Addendum B — redraw procedure (declared before any redraw was run)

Approved resolution of §12. The tool, the field, the recommendation vocabulary, the
baseline procedure and the kill criteria in §§1–11 are **unchanged**. Only the frame
changes, and only along the subject axis.

**Sub-frame.** Tranco top 10,000 (list `K9L5W`, created 2026-08-17), restricted to
domains whose homepage links at least one path matching the product-path pattern already
frozen in `PILOT-PROTOCOL.md` Addendum A1:

```
/product/  /products/  /p/  /pdp/  /dp/  /item/  -p-<digits>
```

**Target.** The first such link in homepage document order, robots-permitted,
canonicalised to scheme + host + path.

**Draw.** Same seed (`20260818`), same draw order, ten qualifying targets, every
rejection recorded with its reason.

**Still forbidden as selection inputs**, unchanged from §6: presence of JSON-LD,
presence of an API or JSON endpoint, whether the page is client-rendered, whether
representations disagree, and whether extraction succeeds. The filter reads a URL path
and nothing else — never markup, never a price, never a network request.

**What this costs the claim, stated plainly:** the result will describe a price
diagnostic on commerce pages, not a general scrape-target diagnostic on arbitrary pages.
That narrower claim is the only one the experiment can support, and the write-up may not
exceed it. The original blind draw and its dispositions remain recorded in
`results/probe/targets.json`; they are not deleted and not reinterpreted.

## 14. Instrumentation defect — unbounded robots.txt fetch (2026-08-18)

**Classification: instrumentation / collection defect. Not a sampling-methodology
change.** The seed, draw order, eligibility rules, product-path patterns, pacing, target
count, field, recommendation rules and kill criteria are all unchanged.

**What happened.** The commerce redraw halted on **draw #34, `sahibinden.com`** (Tranco
rank 1149) and stayed blocked for **106 minutes** with 0.93 s of CPU consumed. The
process held one ESTABLISHED TCP connection to `85.153.138.111` (whois:
`SAHIBINDENBILGI-NET`, TR): the server completed the TLS handshake and then never
responded.

**Root cause.** `urllib.robotparser.RobotFileParser.read()` calls
`urllib.request.urlopen()` with no timeout argument (`urllib/robotparser.py:63`), so it
blocks indefinitely. The project's `httpx` calls all carried a 20 s timeout, but
robots.txt is fetched *first* for every domain, so the one unbounded fetch was the one
that ran on every draw.

**Impact on results: none.** Zero targets had been committed; `results/probe/targets-commerce.json`
did not exist. There are no observations to invalidate. The draw is deterministic, so
restarting from the same seed reproduces the same order and `sahibinden.com` receives a
disposition instead of hanging.

**Repair.** A single shared bounded fetcher, `probe/robots.py`, used by both the target
selector and `probe inspect`: explicit finite timeout, 500 KiB body cap, and named
dispositions — `ROBOTS_TIMEOUT`, `ROBOTS_UNREACHABLE`, `ROBOTS_OVERSIZED`,
`DISALLOWED`, `ALLOWED`. **No failure mode returns permission.** The body is fetched with
the project's bounded HTTP client and handed to `RobotFileParser.parse()`, so stdlib
robots semantics are preserved (401/403 disallow all; other 4xx allow all; 2xx parsed;
5xx refused, matching the stdlib's own `last_checked` behaviour).

Writing those semantics out explicitly caught a second, quieter divergence: an empty
`RobotFileParser` refuses a *missing* robots.txt, where the stdlib allows it. A
regression test pins it.

**Audit.** `RobotFileParser.read()` and unbounded `urlopen()` appear nowhere else in the
project. The paused Arm E collection path (`realworld/collect.py:129`,
`realworld/pilot.py:167`) already fetched robots.txt through a bounded client with a 15 s
timeout and used `parse()`. It was not modified.

**Observability.** The 106-minute silence was itself a defect: the selector emitted
nothing until completion. It now prints one flushed line per draw to stderr —
`draw 34 | sahibinden.com | ROBOTS_TIMEOUT | qualified 0/10` — so a stalled run can be
diagnosed from its output rather than by replaying the deterministic draw. This is
operational output only; it is not read by, and cannot influence, selection.
