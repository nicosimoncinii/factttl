# Python API

FactTTL's Python API evaluates freshness for claim candidates that your
application already has. It does not extract claims from prose, verify their
truth, fetch evidence, read the system clock, or make network requests.

## Install

From a clone of the repository, install the core package with:

```bash
python -m pip install .
```

The optional MCP adapter is not imported by `import factttl`; install the
`mcp` extra only if you use that adapter:

```bash
python -m pip install '.[mcp]'
```

## Evaluate caller-supplied claims

Pass an explicit timezone-aware `evaluation_time` so identical inputs always
produce identical results. `last_checked_at` should only be the time of a
completed qualifying assessment (SUPPORTED or CONTRADICTED), not a time when
the claim was merely extracted or considered.

```python
from datetime import UTC, datetime, timedelta

from factttl import ClaimCandidate, ReviewPolicy, TemporalClass, build_report

report = build_report(
    [
        ClaimCandidate(
            id="release-version",
            text="The current release is 2.4.1.",
            category="software_version",
            temporal_class=TemporalClass.TIME_SENSITIVE,
            last_checked_at=datetime(2026, 9, 20, tzinfo=UTC),
            policy=ReviewPolicy(ttl=timedelta(days=7)),
        )
    ],
    evaluation_time=datetime(2026, 10, 1, tzinfo=UTC),
    include_claim_text=False,
)

row = report.rows[0]
print(row.status)  # STALE
print(row.result.review_due_at)
```

`include_claim_text=False` omits claim text from report rows. It is useful when
reports cross a trust boundary, but the caller still supplies the text to the
process running FactTTL. The core performs no network transmission.

For category policies, parse a local TOML string with `parse_policy_toml`, or
load a file with `load_policy`, then pass the resulting `PolicyConfig` as
`policy_config` to `build_report`. Per-claim policies override category
policies. See [the configuration guide](policy-config.md) and
[in-memory reports](reports.md) for the full policy and report behavior.

## Compatibility

The package is pre-1.0. Public imports are provided for convenient embedding,
but names, signatures, result fields, and policy semantics may change between
minor releases until the project publishes a stable SDK compatibility
guarantee. Pin the FactTTL version in applications where reproducibility
matters.
