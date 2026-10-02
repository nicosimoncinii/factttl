# Proposed technology stack

The initial package scaffold is installable and declares no runtime dependencies. Development tools are managed separately in the `dev` dependency group. The choices below guide future implementation; they are not all current runtime requirements.

## Language comparison

| Language | Strengths for FactTTL | Trade-offs | Decision |
|---|---|---|---|
| Python | Strong AI/NLP ecosystem, approachable contributors, fast CLI and text processing, easy future SDK | Runtime distribution and lower raw throughput | **Primary language** |
| TypeScript | Good CLI ecosystem and broad agent/web integration | Requires Node.js; less direct access to Python's early AI/data ecosystem | Defer as possible future SDK only if justified |
| Go | Excellent portable CLI distribution and concurrency | More work to reach likely early NLP/AI integrations | Not selected |
| Rust | Excellent performance and safety; strong binaries | Higher learning/build cost and slower contributor onboarding; V1 is not throughput-bound | Not selected |

## V0.1 tool choices

| Concern | Proposed choice | Rationale / boundary |
|---|---|---|
| Runtime | Python 3.11+ | Cross-platform; standard library includes TOML parsing |
| Package manager | `uv` with committed lock file | Reproducible installs and environment management in one familiar tool |
| CLI | Typer; Rich for terminal presentation | Small command surface, readable help; core remains callable without CLI |
| Schema validation | Pydantic v2 at input/config boundaries | Explicit validation for untrusted text/provider/config records; keep policy core dependency-light where practical |
| Testing | pytest | Familiar Python ecosystem and parameterized boundary cases |
| Formatter/linter | Ruff format + Ruff check | One fast tool for consistent formatting and common lint rules |
| Type checking | mypy, strict for public/core modules | Catch interface drift in core contracts |
| Logging | Python `logging` standard library | No logging dependency; CLI controls presentation and verbosity |
| HTTP client | HTTPX, optional verification extra only | Modern sync/async support; core must function without it or network access |
| Plugin system | None in V0.1; narrow protocols first | Defer entry-point discovery until multiple adapters prove need |
| Storage | None required in V0.1; file/stdout reports | Local-first, avoids migration and retention commitments prematurely |
| Configuration | TOML, parsed with `tomllib` | Readable and standard-library parser; Pydantic validates semantic values |

## Maintenance and portability

The planned core works on Windows, macOS, and Linux without provider credentials. Optional network providers should declare their dependencies separately. Keep lock-file generation reproducible and document the supported Python version matrix when packaging begins. Do not introduce a JavaScript or Rust implementation just for theoretical performance or integration breadth.

## Deferred decisions

- Exact supported Python minor versions at each release.
- Whether standalone binaries are needed for users without Python.
- Whether Rich remains a required dependency or is an optional extra.
- First verification provider and associated API, cost, licensing, and privacy trade-offs.
- Storage format if repeat scans and `diff` require persisted history.
