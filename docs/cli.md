# Command-line scan

The first CLI command evaluates caller-supplied claims against a local freshness
policy. It does not extract claims from prose, decide whether claims are true,
call a provider, access the network, or read the system clock. The input supplies
an explicit evaluation time, making the result repeatable.

Install the package in an environment, then run:

```text
factttl scan [FILE|-] [--policy PATH] [--format text|json]
```

`FILE` is a UTF-8 JSON document. Omit it or pass `-` to read standard input.
`--policy` optionally selects a local TOML policy file. The default output is
human-readable text; `--format json` emits the versioned machine-readable format.

## Input document

The document has `schema_version: 1`, an explicit timezone-aware ISO 8601
`evaluation_time`, and an ordered `claims` array. Each claim requires non-empty
`text`; all other fields are optional:

```json
{
  "schema_version": 1,
  "evaluation_time": "2026-10-06T12:00:00Z",
  "claims": [
    {
      "id": "release-date",
      "text": "The release is scheduled for October 10.",
      "category": "event",
      "temporal_class": "HIGHLY_VOLATILE",
      "last_checked_at": "2026-10-05T12:00:00+02:00",
      "ttl_seconds": 21600
    }
  ]
}
```

`temporal_class` is one of `STABLE`, `TIME_SENSITIVE`, `HIGHLY_VOLATILE`, or
`UNKNOWN`. `last_checked_at` must be timezone-aware. A per-claim `ttl_seconds`
or `review_disabled: true` overrides category policy; the two cannot be set
together. Non-negative integer TTLs are accepted, including zero. Category
policies use the TOML format described in [policy configuration](policy-config.md).
Unknown fields and invalid/missing required fields are errors. The input order
is preserved, missing IDs become `claim-N`, and duplicate IDs are errors.
Input is limited to 10 MiB, including when read from standard input.

## Output and exit behavior

The JSON output contains `schema_version`, UTC `evaluation_time`, a `counts`
object with all five statuses, `total`, and ordered `rows`. Each row includes
the claim metadata, status, resolved policy (including TTL seconds and reason),
and result timestamps/reason. Timestamps are normalized to UTC with a `Z`
suffix. The output is deterministic for identical input and policy files.

`FRESH`, `STALE`, `UNVERIFIED`, `NOT_REQUIRED`, and `UNKNOWN` are evaluation
results, not command failures; each exits with status 0. Invalid JSON/schema,
invalid policy, or input/configuration I/O errors print an actionable message to
stderr and exit nonzero (status 2). No partial report is printed on failure.
Text output JSON-quotes claim text so embedded newlines and control characters
cannot look like additional report rows. Duplicate JSON keys are rejected to
avoid ambiguous inputs.

Example:

```text
factttl scan claims.json --policy factttl.toml --format json
cat claims.json | factttl scan -
```
