# ADR-001: Primary programming language

- **Status:** Accepted for the planned V0.1 design; revisit only through a superseding ADR.
- **Date:** 2026-10-02

## Context

FactTTL needs a cross-platform CLI, text processing, optional AI/provider ecosystem access, and a contributor-friendly path for a small open source project. The core should remain local and model-agnostic.

## Decision

Use **Python 3.11+** as the primary language. Use `uv` for project/dependency management and lock files. Keep provider-specific dependencies optional. No secondary language is selected for V1.

## Alternatives

- **TypeScript:** strong CLI and ecosystem portability; adds Node.js runtime and has a less direct fit with the Python AI/data ecosystem.
- **Go:** excellent single-binary CLI and concurrency; fewer convenient NLP/AI integrations for likely early contributors.
- **Rust:** strong performance and distribution; higher implementation and contributor cost for a problem whose initial bottleneck is semantic quality, not throughput.

## Consequences

Python offers broad parsing and AI ecosystem access and is easy to prototype, but requires users to have a supported runtime unless later packaging provides standalone binaries. Performance is expected to be sufficient for local text reports. Build distribution and compatibility matrices should be revisited with user evidence.
