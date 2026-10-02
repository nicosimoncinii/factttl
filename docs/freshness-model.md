# Freshness model

## Purpose

Freshness answers: **“Given this review policy and evaluation time, is another check due?”** It does not answer whether a claim is true.

## Temporal classes

| Class | Initial interpretation | Default behavior |
|---|---|---|
| `STABLE` | Expected to change rarely in ordinary contexts | No routine verification TTL; still may be checked when context warrants |
| `TIME_SENSITIVE` | Meaningful chance of change over days or months | Category TTL applies |
| `HIGHLY_VOLATILE` | Can change over minutes, hours, or days | Short category TTL and prominent review due signal |
| `UNKNOWN` | Insufficient evidence to assign a class | No silent “stable” fallback; ask for policy or expose as unknown |

`UNKNOWN` is a state for missing/ambiguous classification, not a volatility class. Classification can be conservative and include rationale. User policy overrides classifier suggestions.

## Initial categories and suggested defaults

All values are **configurable starting points**, not objective expiration dates or guarantees. Domain, jurisdiction, source cadence, and consequences of staleness should determine final policy.

| Category key | Class suggestion | Suggested TTL |
|---|---|---:|
| `software_version` | TIME_SENSITIVE | 7 days |
| `price` | HIGHLY_VOLATILE | 24 hours |
| `company_role` | TIME_SENSITIVE | 30 days |
| `public_role` | TIME_SENSITIVE | 30 days |
| `law` | TIME_SENSITIVE | 30 days |
| `regulation` | TIME_SENSITIVE | 30 days |
| `statistics` | TIME_SENSITIVE | 90 days |
| `market_data` | HIGHLY_VOLATILE | 1 hour |
| `event` | HIGHLY_VOLATILE | 6 hours |
| `availability` | HIGHLY_VOLATILE | 1 hour |
| `product_spec` | TIME_SENSITIVE | 90 days |
| `ranking` | TIME_SENSITIVE | 7 days |
| `news` | HIGHLY_VOLATILE | 6 hours |

The table is a draft baseline, not shipped configuration. A future policy should allow explicit no-TTL/always-review behavior and category overrides.

## Status semantics

- `FRESH`: a relevant verification timestamp exists and the configured interval has not elapsed at evaluation time.
- `STALE`: the interval has elapsed; review is due. It does not mean false.
- `NOT_REQUIRED`: policy says routine freshness review is not applicable (often `STABLE`). This is distinct from “freshly verified.”
- `UNVERIFIED`: no relevant verification record exists.
- `UNKNOWN`: class, category, policy, or timestamp is insufficient to evaluate safely.

Exact boundary semantics (whether equality at TTL is stale) must be specified and tested before V0.1 release. Initial proposal: stale when `evaluation_time >= last_verified_at + TTL`.

## Timestamp rules

Use timezone-aware UTC timestamps in serialized records. Keep `observed_at` (when evidence says the fact applies), `retrieved_at` (when evidence was obtained), and `verified_at` (when a verification attempt was recorded) conceptually distinct. Do not substitute one for another without recording the rule. A future claim can be fresh now but not yet valid; temporal validity is separate from freshness and should remain out of V1 unless required by a concrete use case.

## Aggregate reporting

A future score must disclose its denominator, excluded/unknown count, policy version, and evaluation time. Do not label it an accuracy or truth score. The preferred V0.1 report is counts by status and a per-claim rationale, not one opaque percentage.
