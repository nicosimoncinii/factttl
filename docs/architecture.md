# V1 architecture (proposal)

## Pipeline

```text
Input
  → claim candidate extraction
  → temporal classification
  → category assignment
  → TTL policy resolution
  → freshness evaluation at a supplied time
  → optional verification provider
  → report
```

Keep extraction and verification behind narrow interfaces. Policy evaluation should be deterministic and usable without a model, network, or provider credentials. A report may include unknowns instead of forcing a classification.

## Proposed package boundaries

| Module | Responsibility | Explicitly out of scope |
|---|---|---|
| `models` | Versioned conceptual records and enums for claims, policy, evidence, and reports | Business logic that calls providers |
| `claims` | Claim candidate input and extraction contract; preserve source span when available | Promising complete semantic extraction |
| `classifiers` | Temporal class and category assignment contracts and rationale | Truth adjudication |
| `policies` | Defaults, user overrides, policy resolution, and validation | Hard-coded universal TTLs |
| `freshness` | Deterministic status from timestamps, TTL, and explicit evaluation time | Network access |
| `verification` | Orchestration contract for optional claim checks | Treating a provider response as ground truth |
| `sources` | Provider adapters and provenance capture | Mandatory vendor dependency |
| `reports` | Human and machine-readable summaries, counts, unknown states | Unsupported aggregate “truth scores” |
| `config` | Loading and validating local policy configuration | Secret storage |
| `cli` | Local user interface around public core operations | Independent domain semantics |
| `plugins` (later) | Discovery and lifecycle for optional adapters if demand justifies it | Arbitrary runtime code execution by default |

Do not create a module until there is a concrete responsibility and use case. The names are proposed package boundaries, not empty scaffolding requirements.

## Dependency direction

`cli` and provider adapters depend on core contracts. Core models, policy resolution, and freshness evaluation depend only on the standard library and local inputs. Network libraries belong in optional verification extras. Report formats should serialize the public model without reaching into provider implementations.

## Execution and storage

V1 is a process-local operation over supplied text/claims and policy. No server or database is required. Reports may be written to stdout or a user-selected file. Persistent history should wait until `diff` and repeat-scan use cases establish a data format and retention expectations.

## Failure behavior

- Unknown classification stays unknown and is visible in output.
- Missing verification time cannot be silently replaced with “now” in reproducible evaluations; CLI may default to current UTC but must report it.
- Provider errors remain distinct from stale status and from a negative verification result.
- No provider is called unless selected by the caller or explicit configuration.
