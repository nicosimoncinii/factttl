# ADR-004: Freshness model

- **Status:** Accepted as the central design principle; detailed semantics remain open until V0.1 contract issue is closed.
- **Date:** 2026-10-02

## Context

Age does not determine truth. A useful system needs to distinguish currentness, evidence, and truth while applying review intervals consistently.

## Decision

Model freshness as a policy-based status computed from a relevant verification timestamp, configurable TTL, and explicit evaluation time. Include `STABLE`, `TIME_SENSITIVE`, and `HIGHLY_VOLATILE` sensitivity classes plus explicit unknown/not-required states. Expiry means review is due, not false.

## Alternatives

- Single binary fresh/stale: simple but hides unverified, unknown, and stable/no-check cases.
- Numeric freshness score only: compact but hard to interpret and easy to mistake for truth confidence.
- Volatility decay probability: expressive but difficult to calibrate and explain in an initial release.

## Consequences

The model is explainable and deterministic for fixed inputs, but categories and TTL defaults are policy choices, not universal facts. Boundary behavior, time fields, and aggregate reporting must be specified before release.
