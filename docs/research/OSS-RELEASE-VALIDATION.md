# OSS Release Validation

Release-readiness pass for the `price` + `availability` evidence engine. No product
features added. Sections 2 onward are filled from measurement.

---

## 1. Validation Protocol

**Frozen before any real page was fetched.**

**Population.** Pages where `price` and `availability` are meaningful fields — public
single-product commerce pages. This is a *validation* set on a declared population, not a
prevalence study, so the domain list is declared rather than drawn from a ranking. Earlier
increments established that a rank-list frame yields B2B marketing pages, not PDPs
(`DIAGNOSTIC-RETEST-RESULTS.md` §5).

**Domain list, fixed before inspecting any markup**, chosen for breadth of category and
geography only:

```
argos.co.uk        johnlewis.com      currys.co.uk       screwfix.com
decathlon.co.uk    zalando.co.uk      ikea.com           bol.com
mediamarkt.de      fnac.com           elgiganten.se      bilka.dk
target.com         bestbuy.com        homedepot.com      chewy.com
rei.com            newegg.com         bhphotovideo.com   wayfair.com
canadiantire.ca    jbhifi.com.au      kmart.com.au       flipkart.com
croma.com          noon.com           takealot.com       mercadolivre.com.br
falabella.com      shein.com
```

**Target selection, mechanical and blind to markup:**

1. robots.txt must permit our user agent (bounded fetcher).
2. Homepage must return HTTP 200.
3. Target = first same-host link in homepage document order whose path matches the frozen
   product pattern (`/product/`, `/products/`, `/p/`, `/pdp/`, `/dp/`, `/item/`,
   `-p-<digits>`) **and carries a further path segment**.
4. One target per domain. Every rejection recorded with its reason.

**Forbidden as selection inputs:** whether the engine succeeds, presence of JSON-LD,
presence of an endpoint, representation disagreement, channel count, whether rendering is
needed, or whether the page is likely to be blocked. No disagreement is manufactured, and
no page is chosen because its result is known.

**Adjudication.** Each page is checked by hand against its own source and rendered
content: were found values really present, was obvious evidence missed, is the normalized
value right, is the provenance right, are the relations right, did rendering degrade
correctly, and was a challenge recognised where one occurred. The engine is **not**
required to decide which observation is semantically correct.

**Defect classes:** `CRASH`, `FALSE_FIELD_MATCH`, `MISSED_EVIDENCE`, `NORMALIZATION_ERROR`,
`PROVENANCE_ERROR`, `RELATION_ERROR`, `ACQUISITION_ERROR`, `BLOCK_DETECTION_ERROR`, `OTHER`.
Every genuine defect fixed in this pass gets a regression test. No heuristic is added
merely to improve aggregate numbers.

**Architecture stop condition.** If the field-adapter + normalized-value + observation +
relation abstraction cannot represent required evidence cleanly, this pass STOPS rather
than redesigning around the failure.

### 1a. Frame amendment, declared before any engine call

The frozen procedure produced **5 usable targets from 30 domains**, short of the 20–30
required. Dispositions:

```
DISALLOWED 8 · NO_PRODUCT_LINK 8 · HTTP_403 5 · SELECTED 5
ROBOTS_TIMEOUT 1 · ROBOTS_OVERSIZED 1 · HTTP_429 1 · UNREACHABLE 1
```

Two distinct causes, neither about the engine:

1. **Large retailers refuse robots-respecting clients.** 8 disallow us outright and 5
   return 403 to a plain GET. We do not evade, so those domains are simply unavailable.
   This is a permanent property of the population, not a bug.
2. **Homepages link categories, not products** (8 cases). Step 3 only looked at the
   homepage, which is too shallow for a typical storefront.

**Amendment, applied before the engine was run on any page**, so it cannot be selection on
a known result:

- **Step 3 gains one hop:** if the homepage yields no product-detail link, follow the
  first listing/category link (existing frozen `LISTING_PATH` pattern) and take the first
  product-detail link there.
- **A second declared tranche of 15 smaller/independent storefronts** is added to offset
  domains that refuse access, chosen for category breadth before inspecting any markup.

Everything else is unchanged, and the forbidden selection inputs are unchanged. The
original 30-domain result above is preserved rather than replaced.

## 2. Pages Tested

**8 pages, not the 20–30 required.** The declared 30-domain list plus a 15-domain second
tranche produced 8 usable targets from 45 domains. The shortfall is the population's
property, not a sampling accident: 8 domains disallow our user agent, 5–7 return 403/429
to a plain GET, and we do not evade. **This alone means release readiness could not be
established.**

```
elgiganten.se       /product/…/hp-barbar-dator-15-…/1058450
chewy.com           /chewy-egift-card/dp/226306
newegg.com          /ryzen-7-7700x3d-…/p/N82E16819113941
canadiantire.ca     /en/pdp/noma-…-dehumidifier-…-0438849p.html
mercadolivre.com.br /glossary/P/1                      ← frame artifact, not a product page
lakeland.co.uk      /products/lakeland-10-in-1-tri-ply-only-pan-pro
naturisimo.com      → ohmycream.co.uk/products/westman-atelier-baby-cheeks-…
adafruit.com        /product/6512
```

Each page was inspected for both fields: **16 page-field runs**.

## 3. Field Coverage

`price` and `availability` on all 8 pages. `price` produced values on 4 pages,
`availability` on 5. Three pages produced nothing for either field: two were blocked or
JS-shelled (chewy, newegg) and one was not a product page (the mercadolivre frame artifact).

## 4. Channel Coverage

Recorded, not forced:

```
observations with a value   NETWORK_JSON 42 · RAW_DOM 12 · STRUCTURED_DATA 9 · RENDERED_DOM 5
page-field runs per channel STRUCTURED_DATA 8 · NETWORK_JSON 6 · RAW_DOM 4 · RENDERED_DOM 4   (of 16)
```

`EMBEDDED_STATE` produced **nothing** across the whole set — the first real-world signal
that this channel may be rarely load-bearing on modern storefronts. Unlike the previous
retest, `NETWORK_JSON` was heavily exercised here.

## 5. Reliability

**Zero crashes across 16 runs.** Render outcomes: `OK` 12, `RENDERING_TIMEOUT` 2,
`PARTIAL_RENDER` 1, `BLOCKED_OR_CHALLENGED` 1. Every non-OK outcome produced a report.

## 6. Price Results

- **adafruit.com — fully correct.** `49.95 USD` in RAW_DOM (`a>div>p.price`),
  STRUCTURED_DATA (`script[1]/offers/price`) and RENDERED_DOM, three `EQUAL` relations.
  This is the engine doing exactly what it claims.
- **elgiganten.se — correct after fix.** `4990 SEK` from `script[0]/offers/0/price`.
  Before the boolean fix this page produced 1 real value plus **8 junk observations** from
  `isClubPrice` / `isOutletPrice` flags.
- **canadiantire.ca — wrong.** Eight values from a **financing table**
  (`$100/$1.81`, `$500/$9.04`, `$1000/$18.07`, `$2000/$36.15`) via the unlabelled fallback.
  None is the product price, and the product price was missed. Also normalized as `USD` on
  a Canadian site, because `$` alone maps to USD.
- **chewy, newegg, mercadolivre — no value**, correctly: two are blocked/JS-shelled and one
  is not a product page.

## 7. Availability Results

- **adafruit, elgiganten, lakeland — correct** schema.org values with exact pointers.
- **naturisimo — spurious disagreement.** `In stock` and `Out of stock` were read from a
  **store-locator list** (`div.location-list-item__header`), producing 6 `DIFFERENT`
  relations that do not describe the product's availability.
- **lakeland — other products' data.** Four `dc_in_stock` flags came from
  `/results/0/hits/{0..3}/…`, a **search-results payload for different products**.
- **newegg — one value from a partially rendered page** (`/MainItem/Instock`), plausible
  but unverifiable against a page we could not fully load.

## 8. Network / Embedded Results

`NETWORK_JSON` dominated the observation count (42 of 68) and is where most of the
false matches originated: recommendation and search payloads carry the same key names as
the product. `EMBEDDED_STATE` contributed nothing on any page.

## 9. Blocked-Render Results

The new detection is conservative — a named vendor token anywhere, or interstitial wording
**in visible text only**, or a captcha on an otherwise empty page.

- **newegg.com** is now correctly `BLOCKED_OR_CHALLENGED`. Before this pass its raw body
  literally read *"Are you a human?"* and the engine treated it as an ordinary empty page.
- No ordinary page in the set was misclassified as blocked.
- **chewy.com** returns a 1,163-byte script-only shell with no named marker. It is *not*
  flagged, which is the intended precision trade: unnamed thin pages are left alone.

## 10. Defects Found

| # | Class | Detail |
|---|---|---|
| D1 | `BLOCK_DETECTION_ERROR` | Challenge detection ran on the rendered page only; a blocked **raw HTTP** body was read as an ordinary page |
| D2 | `BLOCK_DETECTION_ERROR` | Marker list missed *"Are you a human?"* |
| D3 | `BLOCK_DETECTION_ERROR` | Interstitial phrases were matched inside `<script>` source, so a page merely *mentioning* the wording could be misclassified |
| D4 | `FALSE_FIELD_MATCH` | Boolean flags whose keys match the price pattern (`isClubPrice: false`) became observations |
| D5 | `FALSE_FIELD_MATCH` | **Other entities on the same page** — search hits, store locators, recommendation carousels, financing tables — are read as the requested field |
| D6 | `NORMALIZATION_ERROR` | `$` maps to USD unconditionally, so Canadian prices are labelled USD |

## 11. Defects Fixed

**D1, D2, D3, D4.** D1 required the only model change in this pass: `Acquisition` gained a
single `http_challenge` string, because the model previously **could not express** "the
cheap fetch was blocked". That is one field, not a redesign.

**D5 and D6 are deliberately not fixed.** D5 needs a notion of *which entity an
observation belongs to*, which the engine does not have; papering over it with selector or
pointer heuristics would be exactly the "heuristic to improve aggregate numbers" this pass
forbids. D6 needs locale evidence the parser does not currently receive.

## 12. Regression Tests Added

```
challenged raw body → no observations, named signal, explicit warning
ordinary raw body   → no challenge signal, observations intact
script mentioning challenge wording → NOT a block, raw evidence survives
boolean price flags → not candidates, real price still found
challenge page      → rendered channels not read, raw evidence intact
captcha on empty page → block;  captcha with real content → not a block
ordinary pages      → never classified as blocked
```

Suite: **227 → 236 passed.**

## 13. Remaining Limitations

1. **D5 — same-page entity confusion.** The most serious. On 2 of 5 pages with
   availability data, the `DIFFERENT` relations were substantially spurious.
2. **D6 — `$` is assumed USD.**
3. **8 pages is not a validation set.** Coverage for `availability` in particular is thin.
4. **`EMBEDDED_STATE` produced nothing at all**, so it remains effectively unvalidated.
5. **Thin, unnamed block pages are not detected** (chewy) — a deliberate precision choice.
6. Robots-respecting access excludes most large retailers, so the reachable population is
   skewed toward smaller storefronts.

## 14. Evidence-Model Assessment

**No redesign required.** All observed evidence was representable: multiple candidates,
absent channels, parse failures, partial and blocked renders, cross-channel relations. D1
was absorbed by adding one field.

D5 is the honest test of the abstraction, and it **passes on representation while failing
on usefulness**: provenance already distinguishes `/results/0/hits/3/…` from
`/data/offers/availability`, so the evidence is there and correctly attributed. What the
engine lacks is any notion of subject scope, so it emits relations between observations
about *different products*. That is a scoping gap, not a modelling failure — and it must be
solved before the relation output can be trusted.

## 15. Quality Gate

```
before:  227 passed · ruff format clean · ruff check clean · mypy clean (52 files)
after:   236 passed · ruff format clean · ruff check clean · mypy clean (52 files)
```

## 16. Final Verdict

Against the release gate: zero unhandled crashes ✓; provenance trustworthy on every case
examined ✓; blocked rendering now represented rather than silently trusted ✓; no
evidence-model redesign required ✓. But **a severe relation defect remains** — D5 makes a
majority of `DIFFERENT` relations spurious on pages carrying search or locator payloads,
and relations are the differentiated primitive. And **`availability` did not survive
meaningful real-world coverage**, because the population would only yield 8 pages.

Four real defects were found and fixed, three of them in block detection that had been
written in this same pass — which is a reasonable measure of how much a single real-world
run still teaches this engine.

**NEEDS NARROW CORRECTNESS FIXES**

The fixes are scoped and do not require new architecture: give observations a notion of
subject scope so other-entity matches stop generating relations (D5); take currency from
page locale rather than assuming `$` is USD (D6); and assemble a validation set that can
actually reach 20–30 pages, which likely means accepting smaller storefronts as the
reachable population and saying so.
