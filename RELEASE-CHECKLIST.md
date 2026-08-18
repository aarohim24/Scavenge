# Scavenge v0.1 Release Checklist

Experimental release, published for technical feedback rather than production use.

## Done

- [x] **Name — `Scavenge`.** PyPI `scavenge` is unclaimed. npm `scavenge` is taken, which is
      irrelevant: no npm package is planned. Repository `aarohim24/Scavenge` exists.
- [x] **License — Apache-2.0**, applied. Chosen for the explicit patent grant, which matters
      for a tool touching structured-data extraction and browser automation.
- [x] **Rename complete.** Package `scavenge/`, console script `scavenge`, MCP server name
      `scavenge`, module `scavenge.mcp`, distribution `scavenge`. Research-only target
      selectors moved to `research/`.
- [x] **Public API corrected.** No relations; `schema_version` 3. The report carries
      observations, normalized values, raw values, channel, provenance, subject scope,
      acquisition status and warnings, and makes no comparison claim.
- [x] **Quality gate.** 250 tests pass; `ruff format --check`, `ruff check` and `mypy` clean.
- [x] **Clean install** verified in a fresh virtualenv: install → `playwright install
      chromium` → CLI runs.
- [x] **MCP verified over stdio** from that fresh environment: single-tool discovery,
      unsafe-URL refusal returned as data, and a real public page returning observations
      with provenance.
- [x] **CLI** is thin over the engine; a test asserts its JSON is byte-identical to the
      engine's.
- [x] **README** written for external developers, with limitations stated before capabilities.
- [x] **Security.** Targets are validated before any request; bodies, waits and response
      counts are bounded; robots.txt is honoured and a failure to read it is never treated
      as permission.
- [x] **CI.** One workflow: pytest, ruff format --check, ruff check, mypy.
- [x] **Hygiene.** `.gitignore` excludes run artefacts, caches and build output.

## Awaiting approval

- [ ] **`git push`.** The repository is public, so this is the point at which the code
      becomes visible. Not performed.
- [ ] GitHub topics: `web-scraping`, `mcp`, `provenance`, `playwright`, `structured-data`,
      `evidence`, `python`.
- [ ] Tag `v0.1.0`.
- [ ] **PyPI — hold.** Publish after a round of external feedback, not before.
- [ ] Show HN — draft at `docs/drafts/SHOW-HN-DRAFT.md`.
- [ ] r/webscraping — draft at `docs/drafts/REDDIT-DRAFT.md`.

## Notes

**On the name.** `Scavenge` reads as scraping rather than evidence or provenance, which is a
slight mismatch with what the tool does: it collects and attributes, and deliberately
refuses to judge. It is memorable and unclaimed, so this is a note rather than an objection.

**On the research directories.** `crawlbench/` and `realworld/` remain at the repository
root. They are research infrastructure, not part of the published engine, and nothing in
`scavenge/` imports them. Their reports live in `docs/research/` and are deliberately left
unrewritten, including their references to pre-rename paths.

## Not performed

No push, no PyPI upload, no Reddit post, no HN submission, no tag, no website, no branding.
