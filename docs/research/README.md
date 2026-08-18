# Research record

Every report that produced this engine, in the order it was written. They are evidence,
not marketing: several of them kill ideas the project had already invested in, and none
has been rewritten to make the current direction look cleaner.

| Report | What it decided |
|---|---|
| `RESEARCH-GATE.md` | Adaptive HTTP/browser crawling already exists (Crawlee). Build a benchmark instead. |
| `CONFIRMATION-PASS.md` | Verified that against pinned Crawlee source; found the `create_default_comparator` footgun. |
| `NOVELTY-GATE.md` | Arm E is a novel combination of known components — and the real world likely disagrees with it. |
| `DEVELOPER-PAIN-GATE.md` | Demand study. Found our benchmark's name already belongs to Firecrawl, and that the real pain is per-target diagnosis. |
| `DIAGNOSTIC-NOVELTY-GATE.md` | Prior-art pass for the diagnostic form. `browser-recon` and `chrome-devtools-mcp` are closer than expected. |
| `PROBE-PROTOCOL.md` · `DIAGNOSTIC-PROTOTYPE-RESULTS.md` | First ten-target run: crashed on 3, missed 2. Not usable. |
| `PROBE-RETEST-PROTOCOL.md` · `DIAGNOSTIC-RETEST-RESULTS.md` | After repairs: 0 crashes, 10/10 agreement — but the evidence engine, not the CLI, was the valuable half. |
| `OSS-MVP-RESULTS.md` | The MVP. Found a correlation defect on the first real page it touched. |
| `OSS-RELEASE-VALIDATION.md` | Real-world validation. Found observations about different entities being compared. |
| `OSS-FINAL-CORRECTNESS.md` | Subject scoping fixed three classes and three more appeared. Comparison removed from the public API. |
| `PILOT-PROTOCOL.md` · `PILOT-PROTOCOL-CHANGES.md` | The paused Arm E real-world pilot and its instrument repairs. |
| `AGENT.md` | The original benchmark charter, kept for the record. |

The benchmark itself (`crawlbench/`) and the paused pilot machinery (`realworld/`) are
research infrastructure. They are not part of the published engine and nothing in
`evidence/` imports them.
