# ADR-002: CLI framework

- **Status:** Accepted for the planned design.
- **Date:** 2026-10-02

## Context

FactTTL is planned to expose a small cross-platform CLI without making the domain core depend on terminal presentation.

## Decision

Use **Typer** for command parsing and **Rich** only for optional human-readable presentation. Keep JSON output plain and stable. CLI is an adapter around the library, not the location of policy semantics.

## Alternatives

- Python `argparse`: standard library, fewer dependencies; viable if the command surface stays tiny.
- Click: mature and explicit; Typer has ergonomic annotations and shares Click's foundation.
- Cyclopts: modern alternative; smaller contributor familiarity than Typer/Click.

## Consequences

Typer/Rich improve help and terminal UX, at the cost of dependencies. Revisit `argparse` if the command surface remains minimal and dependency reduction is more valuable.
