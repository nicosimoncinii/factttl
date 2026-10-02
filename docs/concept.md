# Product concept and scope

## Problem

AI answers often mix durable statements with claims whose validity can change. Most answer pipelines do not make the age of a claim or its review interval explicit. A statement may have been true at generation time and become stale later.

## Target users

- AI and agent engineers building answer pipelines.
- Developers maintaining assistants that cite or retrieve external information.
- Teams that need a review signal for time-sensitive generated content.
- Open source maintainers who want a small, embeddable freshness layer.

## Value proposition

FactTTL makes the freshness expectation for a claim explicit: identify candidate claims, classify how quickly they may change, apply a configurable review interval, and show when a fresh check is due. It helps route verification effort; it does not certify truth.

## Main use cases

1. Scan a draft answer and surface claims about prices, roles, laws, releases, or events that may need a current source.
2. Apply one consistent freshness policy across several model providers.
3. Report which claims are fresh, stale, unknown, or unsupported, with last-check time and source provenance where available.
4. Compare two reports to find newly stale claims (future roadmap).
5. Embed deterministic policy evaluation in a local script or agent workflow (future SDK/integrations).

## Nearby concepts and boundaries

| Concept | Primary question | FactTTL boundary |
|---|---|---|
| Fact checking | Is this claim true or false? | Freshness can prioritize a check; FactTTL does not itself establish truth. |
| RAG | Which context should be retrieved for this query? | Retrieval can supply evidence; FactTTL evaluates claim age and review policy. |
| Web search | What relevant pages can be found now? | Search is a possible provider input, not the freshness model itself. |
| Hallucination detection | Was a claim unsupported or fabricated? | A stale claim can be sourced and true historically; a fresh claim can still be false. |
| Source verification | Is this source authentic/reliable and does it support the claim? | Source quality and claim support are separate dimensions. |
| Knowledge graph | How are entities and relationships represented? | A graph may store claims and timestamps; FactTTL's focus is review due time and reporting. |

## Distinctive principle

**Truth and freshness are independent.** Expiration of a freshness interval means “review due,” not “false.” Freshness is evaluated against a timestamp and a policy, and should be reproducible for the same inputs.

## V1 limits (scope guard)

- One local library and CLI; no hosted service, multi-tenant backend, database server, or cloud infrastructure.
- No general-purpose assistant, answer generation, agent loop, or autonomous action.
- No claim that automated extraction is complete or reliable; represent extraction uncertainty and allow supplied claim candidates.
- No universal fact-checker, truth score, or guarantee that verification proves truth.
- No mandatory LLM, model provider, web search vendor, or API key.
- No knowledge graph, vector database, crawler, browser automation, or continuous monitoring service.
- No automatic legal, medical, financial, or safety certification.
- No hidden verification network calls; providers are explicit and opt-in.

## Naming check (2026-10-02)

Public web search did not surface a major project with the exact FactTTL / factttl name or a clear Fact-TTL repository match. Search did surface a Go package type named `FactTTL`, used for cache TTL configuration, and adjacent AI freshness/grounding projects. Exact PyPI, npm, and GitHub repository availability could not be conclusively confirmed through this search session. This is not legal trademark clearance and does not reserve package or repository names. Retain FactTTL for now; re-check registries and GitHub immediately before publication. No rename is recommended on the evidence available.
