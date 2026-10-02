# Contributing to FactTTL

Thanks for helping shape FactTTL. The repository now includes the minimal Python package scaffold; product features are still under development. Start with an issue or discussion so we can agree on scope before implementation.

## Before starting

1. Read the [README](README.md), [architecture](docs/architecture.md), [freshness model](docs/freshness-model.md), and [roadmap](ROADMAP.md).
2. Check the issue backlog and existing discussions for overlap.
3. For a behavior or architecture change, open an issue first. Changes to accepted architectural choices require an ADR update.

## Development setup

The package supports Python 3.11 or newer and uses `uv` to create a reproducible development environment. Install `uv`, then run:

```console
uv sync --locked
```

Run the quality checks with:

```console
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest
```

To intentionally update dependency versions, edit `pyproject.toml` and run `uv lock`; commit the resulting `uv.lock` with the change. Documentation-only contributions do not require installing the development dependencies.

## Branches

Use short-lived branches from `main`: `feat/<topic>`, `fix/<topic>`, `docs/<topic>`, `refactor/<topic>`, `chore/<topic>`, or `research/<topic>`. `main` is the only long-lived branch. Do not force-push shared branches.

## Commits

Use Conventional Commits, for example `docs: clarify freshness semantics`, `feat: add policy evaluation`, or `fix: handle missing verification time`. Keep each commit focused. Add a scope when useful, such as `docs(model): define stale status`.

## Issue workflow

Issues should state the problem, intended outcome, scope, and acceptance criteria. Label work by type, area, and priority. Research issues should record sources and a recommendation; they should not smuggle implementation into a design task.

## Pull requests

- Link the issue and explain the motivation and user-visible effect.
- Keep changes narrow and update documentation when semantics change.
- State what was reviewed or verified. Do not claim tests passed unless they were run.
- Include a migration or compatibility note for changes to public model semantics.
- Request review before merging; maintainers will use squash merge for a readable history.

## Planned coding standards

The planned Python stack uses Ruff for formatting and linting, strict type checking with mypy, and pytest for tests. Public APIs should have type annotations and docstrings. Keep the core deterministic, local-first, provider-neutral, and free of network access unless a verification provider is explicitly selected. These are planned standards; adopt them when the implementation begins.

## Code of Conduct

Participation is governed by the [Code of Conduct](CODE_OF_CONDUCT.md).
