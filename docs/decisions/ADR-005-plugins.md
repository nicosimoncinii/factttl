# ADR-005: Plugin architecture

- **Status:** Proposed; defer implementation.
- **Date:** 2026-10-02

## Context

The product may eventually accept extractors, classifiers, reporters, and verification providers. A plugin system can aid extensibility but creates discovery, dependency, compatibility, and security costs.

## Decision

Do not build a generic plugin runtime in V0.1. Define narrow Python protocols/interfaces for optional providers first. Consider Python entry-point discovery only after at least two independent adapters demonstrate the need.

## Alternatives

- Generic plugin framework from day one: extensible but premature and harder to secure/support.
- Built-in providers only: simplest, but risks coupling core to vendors.
- Python entry points immediately: standard packaging mechanism, still adds lifecycle/compatibility questions before use cases exist.

## Consequences

Initial integration is explicit and simple. If plugin discovery is later added, document trust boundaries and never execute arbitrary plugins implicitly.
