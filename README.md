# FactTTL

**Give AI claims an expiration date.**

FactTTL is an early-stage project to build a model-agnostic freshness layer for AI answers. It is designed to identify claims whose usefulness can expire, apply configurable time-to-live (TTL) policies, and report when claims should be checked again.

> **Project status: personal testing.** Freshness evaluation, public HTTPS source checks, evidence-backed product/link assessments, source-anchored AI assessments, and persistent correction memory are implemented. General autonomous fact extraction, universal truth verification, account-isolated hosting, and stable SDK guarantees are not implemented.

## Live verification and correction memory

Start the MCP server with `--enable-verification` to enable live checks and a
local SQLite history. It can compare product availability and prices with
explicit structured source data, detect broken links, collect news publication
dates, and remember user-reported corrections. A later FactTTL chat can recall
those corrections before repeating an earlier assertion.

For general claims, the AI compares a claim with source evidence; FactTTL fetches
the source and checks that the supplied excerpt occurs in its extracted text.
That assessment remains fallible and source-relative. An inaccessible source,
CAPTCHA or expired check never becomes a factual verdict. A source's publication
date measures age, not truth. See [verification and memory](docs/verification-model.md).

The plugin cannot force every ChatGPT conversation to consult it or rewrite
ChatGPT's model weights. Select FactTTL in the conversations where you want
these checks. The store is shared by clients of this personal local server;
it is not a multi-user service.

## Automatic buttons in ChatGPT

The experimental [Firefox/Chrome/Edge extension](integrations/chatgpt-extension/README.md)
adds a per-conversation switch and a colored status button next to each distinct
linked source, without an `@FactTTL` mention. It automatically checks
recognized URL-associated prices, stock and discount assertions against public
sources. Open a status button to inspect evidence and unchecked parts. Turning
the switch off removes the buttons and cancels pending checks.

Start the local authenticated bridge with
`python -m factttl.browser_bridge`, or use `scripts/Start-FactTTL-Browser.ps1`
on this Windows test installation. Load the unpacked extension and import the
generated `.factttl/extension-config.json` in its options. The bridge shares the
existing local correction store; it requires no OpenAI API key.

An optional local Ollama model compares URL-associated news assertions with
fetched source text, using validated quotations. Its result describes consistency
with that source, not independently established truth. Configure an installed
model with `--news-model`; see the [news provider](integrations/chatgpt-extension/NEWS-PROVIDER.md).
Arbitrary prose without sources and ambiguous associations remain unverified.
Green applies only to narrowly covered properties; an accessible URL never
proves a whole answer. The extension does not give the model hidden context or
disable a separately selected ChatGPT plugin. A correction can be copied to the
chat explicitly; automatic model-side enforcement requires a supported host
integration. This extension is not installed in Codex's internal browser or
ChatGPT's desktop app.

## What is FactTTL?

See the [compatibility and release policy](docs/release-policy.md) for public
interfaces, schema versions, deprecation and support commitments during 0.x.

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

The current CLI can produce the freshness status, timestamps, TTL, and rationale fields in this example. The `Truth status: UNKNOWN` line is illustrative only: FactTTL does not determine whether a claim is true.

## How the full product is planned to work

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

## Local CLI

```text
factttl scan claims.json [--policy factttl.toml] [--format text|json]
```

`scan` evaluates structured claim candidates supplied by the caller at an
explicit timestamp. It does not extract claims from prose or verify them
against evidence. The JSON input format, policy option, output schema, and exit
behavior are described in the [CLI guide](docs/cli.md). A Python report API is
also available; see [in-memory reports](docs/reports.md) and the
[Python API guide](docs/python-api.md). The optional
[MCP server](docs/mcp.md) exposes the same deterministic evaluation to
compatible agent clients.

## Planned architecture

The current release is a local-first Python library and CLI, with an optional MCP server for agent clients. The core policy engine remains independent of any LLM, search engine, or provider. The proposed tool choices are in [the technology stack](docs/tech-stack.md); see also [Architecture](docs/architecture.md) and the [decision records](docs/decisions/).

For the implemented core's current data handling and the requirements for future providers, see [Privacy and network behavior](docs/privacy-and-network.md).

## Roadmap

- **0.1 — Freshness foundation:** deterministic evaluation, local category policies, in-memory reports, and a CLI for structured caller-supplied claims are implemented.
- **0.2 — Verification providers:** opt-in public HTTPS checks and persistent evidence/correction history are available for personal testing; broader providers remain future work.
- **0.3 — CLI:** structured-claim scanning with text and JSON reports is implemented; policy inspection and report comparison remain future work.
- **0.4 — SDK:** a typed Python embedding API is available; compatibility guarantees remain pre-1.0.
- **0.5 — Integration layer:** a read-only MCP adapter is available; other agent adapters and managed ChatGPT hosting remain future work.
- **1.0 — Stable freshness engine:** versioned model and policy semantics, documented limitations, and a compatibility commitment.

Future shareable features include a freshness summary/badge and `factttl diff` for changes in status between reports. These are roadmap ideas, not commitments or existing features.

## Integrations

The optional MCP adapter works with compatible local stdio clients and with
clients that can reach a secured Streamable HTTP endpoint. To connect ChatGPT,
you must run the HTTP transport somewhere ChatGPT can reach, or use an
appropriate private MCP tunnel; this repository does not host or deploy that
endpoint for you. See the [MCP integration guide](docs/mcp.md) and OpenAI's
[current guide for custom MCP servers](https://developers.openai.com/plugins/build/app-quickstart).
Other potential integration points include Claude Code, Codex, Cursor, Gemini
CLI, and OpenCode. Integrations should call the same model-agnostic core rather
than own freshness semantics.

## Contributing

The project is early-stage and its API may change before 1.0. Read [CONTRIBUTING.md](CONTRIBUTING.md), [the roadmap](ROADMAP.md), and the open issues before proposing implementation work. The initial backlog is tracked in [docs/backlog.md](docs/backlog.md).

## License

FactTTL is planned to use the [MIT License](LICENSE).
