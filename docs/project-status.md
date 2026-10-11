# Implementation status — 2026-10-09

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
| #18 | Public imports, offline embedding and deprecation expectations documented in `docs/python-api.md` and `docs/release-policy.md` | Reviewed |
| #19 | Native MCP answer checks and passive browser indicators implemented; maintenance/coverage evaluation across other hosts remains open | Open |
| #20 | `docs/report-diff-design.md` defines denominator, unknowns, policy/time context and sharing restrictions; reviewed proposal, command not implemented | Design reviewed |
| #21 | Compatibility, semantic versioning, security and release expectations documented in `docs/release-policy.md`; no 1.0 release claimed | Reviewed |

## Current browser work

- Firefox-specific manifest, shared Chromium sources, per-chat opt-in switch.
- Passive browser behavior: no composer writes, Send interception, synthetic
  clicks, or correction follow-ups. Model-visible verification uses MCP tools.
- Distinct source indicators and focused evidence sheets; duplicate citations
  to the same source do not require additional indicators.
- Country/language preferences are hints, not GPS or personalized checkout data.
- Amazon ASIN recommendations request current public stock and observed price.
- Optional local Ollama assessment compares a URL-associated news assertion with
  the fetched source. Conclusions require citations in that source and remain
  attributed to AI source-consistency assessment.
- Source dates, accessibility and model readiness never prove truth.
- Optional Bing RSS discovery submits a bounded topic query; country remains an
  interpretation/cache hint and language affects the source request, without a
  guarantee of geographically targeted search. Up to two discovered pages are
  read through the protected HTTPS fetcher. RSS snippets are not evidence. Search is disabled by
  default and its outbound query is disclosed in settings.
- Up to three supplied sources for one assertion are compared once each. Decisive
  conflicts remain inconclusive. Grounded assessments retain their source or
  excerpt scope when other evidence is missing; unread URLs do not inherit a
  different source's verdict. Long sources use an explicitly limited contiguous
  1,500-character window, shown as partial evidence in the UI.
- Qwen3:4b through local Ollama supports CPU, balanced and extended profiles.
  The full CPU adapter completed a synthetic contradiction check in 30.53 seconds
  on the development PC; this is not an accuracy or universal hardware benchmark.
- Actual public NASA source checks returned scoped support in 24.44 seconds and
  contradiction in 21.26 seconds with validated quotations using CPU inference;
  [useful verification](useful-verification.md) records the assertions and limits.

## Remaining product work

1. Broaden claim extraction and assess source relevance/independence. Automatic
   discovery recognizes bounded public-role statements, geographically scoped
   legal/obligation statements, and announcements/releases of recognized public
   entities even without the word "news" or a supplied URL. Unknown private
   subjects, opinions, questions and hypotheses are excluded. This conservative
   category gate does not certify every factual sentence, perfectly detect
   private information, or establish independence of publisher domains.
2. Signed Firefox distribution and a simpler normal installation experience.
3. Locale-specific merchant coverage and delivery destination confirmation.
4. Evaluate native MCP tool selection across supported hosts and model versions.
   FactTTL returns saved findings, evidence and required revisions through
   `verify_answer` and `verify_recommendations`; the host/model still decides
   whether to invoke them and FactTTL cannot change provider memory or weights.
5. Release implementation, account isolation for shared hosting,
   broader end-to-end coverage across browsers and provider/model evaluations.
