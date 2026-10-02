# Git and GitHub workflow

## Branching

Use trunk-based development with `main` as the only long-lived branch. Work in short-lived branches named `feat/<topic>`, `fix/<topic>`, `docs/<topic>`, `refactor/<topic>`, `chore/<topic>`, or `research/<topic>`. Avoid a permanent `develop` branch; it duplicates integration state for a small project and delays feedback.

## Commits

Use Conventional Commits: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`, `build:`, `ci:`, or `research:`. Keep commits focused and imperative after the type. Add a scope when useful.

## Pull requests

- One issue or coherent change per PR; link the issue.
- Explain motivation, scope, compatibility impact, and validation performed.
- Update docs/ADR when public semantics or architecture change.
- Require maintainer review before merge when contributors beyond the owner are active.
- Prefer squash merge; delete merged topic branches.

## Initial repository protections

GitHub is configured with Issues and Discussions enabled and `main` as the default branch. The active `Protect main branch` ruleset targets the default branch and blocks force pushes and deletion. It does not require pull requests or status checks yet; add review requirements when a second maintainer can review contributions. Do not create a `develop` branch.

## Proposed topics

`ai`, `llm`, `ai-agents`, `freshness`, `temporal-data`, `fact-checking`, `cli`, `open-source`, `knowledge`. Avoid `rag` until an integration is real; the project is adjacent to retrieval, not a RAG implementation.
