# V1 architecture (proposal)

## Implemented personal test version

The freshness/config/report/CLI modules remain offline. Opt-in MCP verification
uses `web_verifier` for bounded public HTTPS observations, `verification` for
validated evidence records, and `verification_store` for durable SQLite history
and conservative reuse decisions. `mcp_verification` coordinates native answer
and recommendation checks, recalls history before live work, and returns
structured revisions directly to the calling model. The optional tools are
enabled explicitly with `--enable-verification`; the default server stays
offline. The local store serves one user's connected clients and is not
tenant-isolated.

No general truth oracle or complete free-form claim extraction is implemented.
The native answer tools perform bounded extraction for supported URL-associated
product properties and configured news patterns. Other semantic comparisons
come from the calling AI, anchored to a quote fetched from the source.

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
| `mcp_server` / `mcp_verification` (optional) | Expose freshness, structured answer checks and local correction history over stdio or Streamable HTTP | Composer injection, guaranteed host tool selection, or unprotected public hosting |
| `plugins` (later) | Discovery and lifecycle for optional adapters if demand justifies it | Arbitrary runtime code execution by default |

Do not create a module until there is a concrete responsibility and use case. The names are proposed package boundaries, not empty scaffolding requirements.

## Dependency direction

`cli` and provider adapters depend on core contracts. Core models, policy resolution, and freshness evaluation depend only on the standard library and local inputs. Network libraries belong in optional verification extras. Report formats should serialize the public model without reaching into provider implementations.

## Execution and storage

Freshness evaluation and report construction are process-local operations over
supplied claims and policy. They do not need a database or provider. The
optional MCP wrapper can expose this operation to a stdio client or a Streamable
HTTP endpoint; any remotely reachable endpoint needs deployment-level
authentication and transport security. Opt-in verification uses a local SQLite
database for evidence and correction history. Reports may be written to stdout
or a user-selected file.

## Failure behavior

- Unknown classification stays unknown and is visible in output.
- Missing verification time cannot be silently replaced with “now” in reproducible evaluations; CLI may default to current UTC but must report it.
- Provider errors remain distinct from stale status and from a negative verification result.
- No provider is called unless selected by the caller or explicit configuration.
