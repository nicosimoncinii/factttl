# FactTTL

**Give AI claims an expiration date.**

FactTTL is an early-stage project to build a model-agnostic freshness layer for AI answers. It is designed to identify claims whose usefulness can expire, apply configurable time-to-live (TTL) policies, and report when claims should be checked again.

> **Project status: early development.** The minimal Python package scaffold is in place. No scanner, verifier, CLI, SDK, or integrations are implemented yet.

## What is FactTTL?

Facts have different rates of change. A statement about water boiling at sea level is usually stable; a software release, company role, price, legal rule, or event date can become outdated. FactTTL treats freshness as a separate dimension of a claim and makes the review interval explicit.

FactTTL is intended to help developers and agent builders decide **which claims need a fresh check, when they need one, and what evidence was checked**. It is not a general-purpose assistant and does not promise that a claim is true.

## Why does this matter?

An answer can be factually correct when generated and still be stale when read later. Retrieval, citations, and confident language do not by themselves establish that time-sensitive information remains current. A freshness policy makes this risk visible and gives systems a consistent way to prioritize re-verification.

## Conceptual example

```text
Claim:            "X is the CEO of company Y."
Temporal class:   TIME_SENSITIVE
Category:         company_role
Suggested TTL:    30 days (configurable default)
Last verified:    2026-09-20
Freshness status: STALE (as of 2026-10-22)
Truth status:     UNKNOWN
```

The dates and output above illustrate the planned model only; they are not produced by a working tool.

## How it is planned to work

```text
Input text or structured claims
  → claim candidates
  → temporal class and category
  → configured freshness policy
  → status at an explicit evaluation time
  → optional verification by a configured provider
  → human-readable or machine-readable report
```

Claim extraction and verification are fallible and provider-dependent. The report should preserve that uncertainty and never silently turn freshness into truth.

## Freshness categories

| Class | Meaning | Typical handling |
|---|---|---|
| `STABLE` | Expected to remain valid absent unusual change | No routine freshness check by default |
| `TIME_SENSITIVE` | Can change on a days-to-months horizon | Apply a category TTL |
| `HIGHLY_VOLATILE` | Can change within hours or days | Short TTL; prioritize recent evidence |

These are operational defaults, not claims about truth. The initial category and policy proposal is in [the freshness model](docs/freshness-model.md).

## Example TTL policies

Illustrative defaults only; users must be able to override them for their domain and risk tolerance.

| Category | Suggested default |
|---|---:|
| `software_version` | 7 days |
| `price` | 24 hours |
| `company_role` | 30 days |
| `public_role` | 30 days |
| `law` / `regulation` | 30 days |
| `statistics` | 90 days |
| `market_data` | 1 hour |
| `event` | 6 hours |
| `availability` | 1 hour |
| `product_spec` | 90 days |
| `ranking` | 7 days |
| `news` | 6 hours |

An expired TTL means “review due,” not “false.”

## Planned CLI (not implemented)

```text
factttl scan answer.md
factttl verify answer.md
```

`scan` is planned to identify claim candidates and report temporal sensitivity. `verify` is planned to request evidence only for claims that policy says need review. These commands are target UX, not usable commands today.

## Planned architecture

The first release is intended as a local-first Python library and CLI, with no server or required cloud account. Its core model and policy engine should remain independent of any LLM, search engine, or provider. The proposed tool choices are in [the technology stack](docs/tech-stack.md); see also [Architecture](docs/architecture.md) and the [decision records](docs/decisions/).

## Roadmap

- **0.1 — Freshness foundation:** accept text and structured claim candidates; classify temporal sensitivity and category; apply TTL policies; produce a report.
- **0.2 — Verification providers:** define a provider contract and add explicitly configured verification adapters.
- **0.3 — CLI:** deliver a cross-platform CLI for scanning, policy inspection, and report output.
- **0.4 — SDK:** expose a stable Python API after the core model has been exercised.
- **0.5 — Integration layer:** explore MCP and agent-tool adapters; keep optional and provider-neutral.
- **1.0 — Stable freshness engine:** versioned model and policy semantics, documented limitations, and a compatibility commitment.

Future shareable features include a freshness summary/badge and `factttl diff` for changes in status between reports. These are roadmap ideas, not commitments or existing features.

## Integrations

Potential future integration points include Claude Code, Codex, Cursor, Gemini CLI, OpenCode, MCP, a REST API, and Python/JavaScript SDKs. None is implemented. Integrations should call the same model-agnostic core rather than own freshness semantics.

## Contributing

The project is in design stage. Read [CONTRIBUTING.md](CONTRIBUTING.md), [the roadmap](ROADMAP.md), and the open design issues before proposing implementation work. The initial backlog is tracked in [docs/backlog.md](docs/backlog.md).

## License

FactTTL is planned to use the [MIT License](LICENSE).
