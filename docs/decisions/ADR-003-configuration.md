# ADR-003: Configuration format

- **Status:** Accepted for the planned design.
- **Date:** 2026-10-02

## Context

Users need readable category TTL overrides. The first release should avoid a custom configuration language and should not require JSON Schema tooling.

## Decision

Use **TOML** for local configuration. The standard library parser (`tomllib`) is available in the selected Python baseline. Use **Pydantic v2** at configuration/input boundaries for semantic validation; keep the deterministic policy evaluator isolated from parsing concerns.

## Alternatives

- YAML: familiar, but needs a parser dependency and has multiple implicit typing rules.
- JSON: standard and widely supported, but less pleasant for hand-edited config and comments.
- Pydantic Settings/env-only: useful for process settings, less appropriate as the main human-edited policy file.

## Consequences

TOML keeps configuration local and readable. Validation rules and schema versioning still need to be specified; `tomllib` only parses syntax and does not validate FactTTL semantics.
