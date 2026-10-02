# Architecture

This is a pointer to the maintained design in [`docs/architecture.md`](docs/architecture.md). The system is not implemented.

## Design constraints

- A small, local-first Python library and CLI; no service infrastructure in V1.
- Deterministic freshness policy evaluation, separate from probabilistic claim extraction and verification.
- Model- and provider-agnostic core; network access occurs only through an explicitly selected verification provider.
- No database server. Any later local persistence must be justified by real workflows.
- Reports must distinguish freshness from truth, confidence, and source quality.
