# Implementation status — 2026-10-07

This is a personal testing release. Implemented behavior is distinct from a
stable SDK, a signed Firefox release, or independent verification of world facts.

| Issues | Implementation and evidence | Status |
| --- | --- | --- |
| #1–#6 | Freshness model, candidate/report records, policy precedence, aware timestamps and expiry boundaries; `docs/freshness-model.md`, `docs/reports.md`, freshness/report tests | Implemented; review in the integration PR |
| #8 | Pure deterministic freshness evaluator and boundary tests | Implemented |
| #9 | Versioned TOML policy with strict validation and overrides | Implemented |
| #10, #16 | Caller-supplied candidates, versioned JSON reports, preserved unknowns | Implemented |
| #11–#13 | Optional live HTTPS adapter, provenance contract, guarded retrieval and persistent corrections; ADR-006 | Implemented for personal testing |
| #14–#15 | Offline CLI scan, stdin/files, explicit exit semantics | Implemented |
| #17 | Network/privacy documentation and ignored local credentials | Implemented |
| #18 | Public imports and embedding docs exist; stable support/deprecation commitments remain preliminary | Open |
| #19 | MCP and browser extension workflows implemented; maintenance/coverage evaluation across other agents remains open | Open |
| #20 | Per-reference status buttons exist; scan-to-scan report diff and shareable public badge do not | Open |
| #21 | Pre-1.0 limitations documented; release/support policy for 1.0 is unfinished | Open |

## Current browser work

- Firefox-specific manifest, shared Chromium sources, per-chat opt-in switch.
- Distinct source indicators and focused evidence sheets; duplicate citations
  to the same source do not require additional indicators.
- Country/language preferences are hints, not GPS or personalized checkout data.
- Amazon ASIN recommendations request current public stock and observed price.
- Optional local Ollama assessment compares a URL-associated news assertion with
  the fetched source. Conclusions require citations in that source and remain
  attributed to AI source-consistency assessment.
- Source dates, accessibility and model readiness never prove truth.

## Remaining product work

1. Discover and compare independent sources for claims without supplied URLs.
2. Signed Firefox distribution and a simpler normal installation experience.
3. Locale-specific merchant coverage and delivery destination confirmation.
4. Host-supported model context: a visual badge alone cannot teach ChatGPT to
   consult corrections in every future conversation. Currently a correction can
   be copied explicitly, or retrieved through a selected MCP tool.
5. Stable release and support policy, account isolation for shared hosting,
   broader end-to-end coverage across browsers and provider/model evaluations.
