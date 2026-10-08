# ADR-006: Verification provider architecture

- **Status:** Accepted for personal testing; future providers may extend the contract.
- **Date:** 2026-10-02

## Context

Freshness evaluation should work offline, but optional verification requires external evidence providers with different latency, privacy, coverage, and reliability properties.

## Decision

Keep provider calls behind an optional adapter contract. Provider selection is explicit; core logic remains network-free. A verification record includes outcome, provider identity/version, evidence provenance, retrieval/verification timestamps, and operational errors separately.

## Alternatives

- One mandatory search vendor: simpler first integration, but creates lock-in and required credentials.
- Let each classifier call the web directly: convenient initially, but mixes concerns and makes provenance/errors inconsistent.
- No provider abstraction: smallest initial surface, but makes later providers difficult to add consistently.

## Consequences

The abstraction has some design cost and should remain small. Provider outcomes
are evidence assessments, not truth guarantees. The first implementation uses
explicitly enabled, bounded public HTTPS retrieval without credentials or a
paid search vendor. Structured merchant data supports narrow product-property
comparisons; semantic claim assessments remain attributed to the calling AI
and require a quote validated against freshly fetched source text. SQLite retains
contradictions across chats and errors. The offline freshness core is unchanged.
