# In-memory freshness reports

`factttl.report.build_report` evaluates claim candidates supplied by the
calling application. It performs no extraction, verification, network access,
or clock lookup. The caller must pass one explicit, timezone-aware
`evaluation_time` so repeated inputs produce the same report.

```python
from datetime import UTC, datetime

from factttl.config import load_policy
from factttl.freshness import TemporalClass
from factttl.report import ClaimCandidate, build_report

policy = load_policy("factttl.toml")
report = build_report(
    [
        ClaimCandidate(
            id="release-date-1",
            text="The release is scheduled for October 10.",
            category="event",
            temporal_class=TemporalClass.HIGHLY_VOLATILE,
        )
    ],
    policy_config=policy,
    evaluation_time=datetime.now(UTC),  # application chooses and records this
)

for row in report.rows:
    print(row.id, row.status, row.policy.reason)
print(report.counts, report.total)
```

`ClaimCandidate` contains caller-provided text, optional identifier/category/
temporal class/check timestamp, and an optional per-claim `ReviewPolicy`.
Per-claim settings override category settings from `PolicyConfig`; the shared
resolver then applies the documented `STABLE` fallback. Omit `policy` when
there is no per-claim override.

Rows retain input order. Explicit IDs must be unique; a missing ID becomes
`claim-N`, where `N` is its one-based position in the input. Thus generated IDs
remain stable for a fixed ordered input, but callers should supply IDs when
they need identity across reordered reports. Duplicate explicit/generated IDs
raise `ValueError` instead of silently associating results with the wrong
claim.

Each row exposes `status`, `result` (including its evaluation time, TTL,
timestamps, and reason), and the resolved `policy`, whose `reason` records
whether the decision came from a per-claim policy, category policy, or class
fallback. Every defined `FreshnessStatus` appears in `report.counts`, including
statuses with zero rows; `report.total` counts all rows. Unknown and
unverified candidates remain visible. There is deliberately no score or truth
field: `STALE` means review is due, not that a claim is false.

Claim text is included by default so reports are useful without looking up a
separate input list. Use `include_claim_text=False` when reports cross a privacy
boundary; metadata and rationale remain available, but the text is omitted.
This in-memory API does not define JSON serialization; the versioned machine
readable format is a separate concern.
