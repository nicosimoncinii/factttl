# Report comparison and shareable summary design

Status: review proposal; the diff command and public badge are not implemented.

## Identity and comparison

Compare two schema-version-1 reports by explicit claim ID, not position, wording
similarity or model guesses. Reject duplicate IDs and unsupported schemas.
Generated `claim-N` identifiers are reliable only when the original input order
is unchanged. Changed text under the same ID is a changed candidate, not evidence
that an earlier statement became false.

Report added/removed candidates, status transitions and policy changes separately.
Preserve UNKNOWN and UNVERIFIED as explicit transitions. A change to TTL or
evaluation time must be displayed alongside a freshness status change; such a
change may be policy-driven rather than a change in source evidence.

## Summary

A shareable summary displays total candidates, counts of FRESH, STALE, UNKNOWN,
UNVERIFIED and NOT_REQUIRED, evaluation time and policy context. All candidates
remain in the denominator. Unknown candidates never increase a freshness
percentage. Prefer counts to a score; any optional ratio must be labeled
`FRESH / all candidates`, including unknown and unverified candidates.

Freshness counts do not measure truth, verification coverage or extraction
completeness. A badge describing source verification must be separately named
and disclose the assessed properties and source count.

## Privacy and acceptance

An exported badge contains counts and context only, without candidate text,
URLs, credentials or local paths. XML text is escaped; exports contain no
scripts, remote assets or tracking requests. Sharing is an explicit user action.

Before implementation, review schema validation, claim identity, policy-change
disclosure, unknown denominators and privacy examples. The CLI proposal is
`factttl diff before.json after.json --format json`; no provider runs as a
side effect of comparison.
