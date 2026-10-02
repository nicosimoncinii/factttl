# ADR-004: Freshness model

- **Status:** Accepted. The normative input, policy, status, and timestamp rules are in [`../freshness-model.md`](../freshness-model.md).
- **Date:** 2026-10-02

## Context

Age does not determine truth. A useful system needs to distinguish currentness, evidence, and truth while applying review intervals consistently.

## Decision

Model freshness as a policy-based status computed from a qualifying check timestamp, a resolved TTL policy, and an explicit evaluation time. Include `STABLE`, `TIME_SENSITIVE`, and `HIGHLY_VOLATILE` sensitivity classes plus explicit `UNKNOWN`, `NOT_REQUIRED`, and `UNVERIFIED` states. Expiry means review is due, not false. Resolve explicit per-claim policy before category policy, then use the class default; a category TTL applies to `STABLE`, while an explicit per-claim disable overrides it. Unresolved non-stable policy remains unknown. A completed `SUPPORTED` or `CONTRADICTED` evidence assessment can reset the interval; inconclusive/error attempts and extraction alone cannot. Timestamps must be timezone-aware, evaluation time is supplied by the caller, and equality at the deadline is stale.

## Alternatives

- Single binary fresh/stale: simple but hides unverified, unknown, and stable/no-check cases.
- Numeric freshness score only: compact but hard to interpret and easy to mistake for truth confidence.
- Volatility decay probability: expressive but difficult to calibrate and explain in an initial release.

## Consequences

The model is explainable and deterministic for fixed inputs, but categories and TTL defaults are policy choices, not universal facts. Invalid naive timestamps and negative TTLs are validation errors; a check timestamp later than evaluation time produces `UNKNOWN`. The core remains separate from text extraction, verification, and temporal-validity checks.
