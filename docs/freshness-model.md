# Freshness model

## Purpose

Freshness answers: **“Given this review policy and evaluation time, is another check due?”** It does not answer whether a claim is true. The result is deterministic for the same claim record, resolved policy, and evaluation time.

## Temporal classes

| Class | Initial interpretation | Default behavior |
|---|---|---|
| `STABLE` | Expected to change rarely in ordinary contexts | No routine verification TTL; still may be checked when context warrants |
| `TIME_SENSITIVE` | Meaningful chance of change over days or months | Category TTL applies |
| `HIGHLY_VOLATILE` | Can change over minutes, hours, or days | Short category TTL and prominent review due signal |
| `UNKNOWN` | Insufficient evidence to assign a class | No silent `STABLE` fallback; ask for policy or expose as unknown |

`UNKNOWN` is a state for missing or ambiguous classification, not a volatility class. Classification can be conservative and include a rationale. An explicit user TTL takes precedence over a classifier suggestion.

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

These are draft examples, not shipped configuration.

## Input contract

The core evaluator works on one structured claim at a time. Text extraction and verification providers are outside this contract.

| Field | Required | Meaning |
|---|---|---|
| `text` | Yes | Claim text. It is treated as opaque input by the freshness evaluator. |
| `category` | No | Policy key used to find a configured TTL. |
| `temporal_class` | No | `STABLE`, `TIME_SENSITIVE`, `HIGHLY_VOLATILE`, or `UNKNOWN`; may be suggested by a classifier or set by the caller. |
| `last_checked_at` | No | Time of the latest completed evidence assessment. Only `SUPPORTED` or `CONTRADICTED` assessments qualify; `INCONCLUSIVE`, `ERROR`, and extraction alone do not reset the interval. This timestamp does not mean the claim was supported. |
| `ttl` | No | Per-claim duration override. This is a policy value, not a property inferred from truth. |

The caller supplies an explicit `evaluation_time`; the core does not read the system clock. A claim identifier may be supplied by a surrounding record/report layer but is not needed to calculate freshness.

The evaluator returns a status, the evaluation time, the resolved TTL (if any), the last qualifying verification time (if any), the next review time (if calculable), and a human-readable reason. Freshness results do not contain or infer a truth value.

## TTL policy resolution

Resolve one effective policy in this order:

1. Per-claim `ttl` override.
2. Configured TTL for the claim's `category`.
3. If the resolved class is `STABLE` and no TTL was configured, routine review is disabled.
4. Otherwise, if no TTL can be resolved, the policy is insufficient and freshness is `UNKNOWN`.

An explicit policy disable for the claim or category also means routine review is `NOT_REQUIRED`. A missing category or missing TTL for a non-stable claim must never silently imply `STABLE` or `NOT_REQUIRED`. An explicit TTL is sufficient to evaluate a claim even if its temporal class is `UNKNOWN`.

Category suggestions and classifier outputs do not override an explicit caller policy. The concrete policy file syntax and category defaults are defined separately from this decision procedure.

## Status semantics and decision order

Statuses are mutually exclusive:

- `NOT_REQUIRED`: resolved policy explicitly disables routine review, or the class is `STABLE` with no TTL override. No verification timestamp is needed. This is not the same as “freshly verified.”
- `UNKNOWN`: policy cannot be resolved safely, the class/category/policy is ambiguous, or a timestamp is in the future relative to evaluation time. Include a reason so callers can distinguish these cases.
- `UNVERIFIED`: a review interval applies but no qualifying verification timestamp exists.
- `STALE`: a qualifying timestamp exists and the review deadline has been reached or passed. This means review is due; it does not mean false.
- `FRESH`: a qualifying timestamp exists and the review deadline has not been reached.

Apply the decision order above: resolve policy first; return `NOT_REQUIRED` if review is disabled; return `UNKNOWN` if required policy or temporal data cannot be evaluated; return `UNVERIFIED` if there is no qualifying timestamp; otherwise compare the deadline with evaluation time.

For a resolved TTL, calculate:

```text
review_due_at = last_checked_at + ttl
STALE when evaluation_time >= review_due_at
FRESH when evaluation_time < review_due_at
```

Equality is therefore stale. A zero-length TTL is valid and is immediately stale at or after `last_checked_at`.

## Timestamp and duration rules

- `evaluation_time` is required and must be timezone-aware. The evaluator never substitutes the current system time.
- Serialized timestamps use UTC (`Z`); timezone-aware offsets are accepted on input and normalized to UTC.
- Naive timestamps and negative TTLs are invalid input and should produce a clear validation error rather than a freshness status.
- A `last_checked_at` later than `evaluation_time` is inconsistent temporal data: return `UNKNOWN` with a clock-skew/future-timestamp reason, not `FRESH`.
- Keep `observed_at` (when evidence says the claim applies), `retrieved_at` (when evidence was obtained), and `last_checked_at` (when a qualifying evidence assessment was completed) distinct. Do not substitute one for another without recording the rule.
- A future claim can be fresh now but not yet valid; temporal validity is separate from freshness and remains outside V1.

## Aggregate reporting

A future score must disclose its denominator, excluded/unknown count, policy version, and evaluation time. Do not label it an accuracy or truth score. The preferred V0.1 report is counts by status and a per-claim rationale, not one opaque percentage.
