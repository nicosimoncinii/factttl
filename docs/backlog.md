# Initial project backlog

Planning backlog only. These issues have **not** been created on GitHub because GitHub authentication is unavailable. Milestone titles and issue labels below are the proposed initial set.

## Milestones

| Milestone | Purpose |
|---|---|
| 0.1 — Freshness foundation | Agree on core model and produce local freshness reports |
| 0.2 — Verification providers | Add an opt-in, provenance-preserving provider boundary |
| 0.3 — CLI | Make scanning and reports usable cross-platform |
| 0.4 — Python SDK | Stabilize library API |
| 0.5 — Integration layer | Evaluate MCP and agent adapters |
| 1.0 — Stable freshness engine | Freeze semantics and establish release commitments |

## 0.1 — Freshness foundation

### Define claim and report data contract
**Scope:** Specify identifiers, text/span, category/class, timestamps, status, rationale, and schema version. **Acceptance:** docs cover unknown and malformed inputs; examples are conceptual; no truth field is inferred from age. **Labels:** `area: claims`, `type: research`, `priority: high`.

### Specify temporal classification taxonomy
**Scope:** Define class/category meanings and how uncertain classifications are represented. **Acceptance:** taxonomy covers current categories, user overrides, and an `UNKNOWN` outcome; docs distinguish suggestion from truth. **Labels:** `area: classification`, `type: research`, `priority: high`.

### Specify TTL policy precedence and defaults
**Scope:** Define category defaults, user overrides, fallback, and disabled/not-required behavior. **Acceptance:** precedence is deterministic; defaults documented as configurable; no category silently becomes stable. **Labels:** `area: freshness`, `type: research`, `priority: high`.

### Specify timestamp and boundary semantics
**Scope:** Define UTC, verification time, evaluation time, missing time, and equality at expiry. **Acceptance:** examples cover before/at/after expiry and timezone offsets. **Labels:** `area: freshness`, `type: research`, `priority: high`.

### Define claim extraction contract and limitations
**Scope:** Separate claim candidates from verified facts; support supplied candidates alongside extraction. **Acceptance:** false positives, omissions, spans, and unsupported text are represented in docs; no completeness promise. **Labels:** `area: claims`, `type: research`, `priority: high`.

### Define report schema and unknown-state behavior
**Scope:** Specify per-claim fields, summary counts, warnings, and machine-readable serialization. **Acceptance:** stale is never described as false; unknowns/errors remain visible; a summary score is deferred. **Labels:** `area: reports`, `type: feature`, `priority: medium`.

### Scaffold Python package and development tooling
**Scope:** Create minimal installable package skeleton after contract decisions. **Acceptance:** supported Python versions, uv workflow, Ruff, mypy, pytest, and CI are documented and reproducible; no provider dependency in core. **Labels:** `area: core`, `type: feature`, `priority: high`.

### Implement deterministic freshness policy evaluation
**Scope:** Evaluate status from verification time, TTL, and explicit evaluation time. **Acceptance:** boundary, missing data, stable/not-required, and timezone behavior are covered by tests; no network calls. **Labels:** `area: freshness`, `type: feature`, `priority: high`.

### Add initial local policy configuration
**Scope:** Load user-editable TOML policy with schema validation. **Acceptance:** defaults and overrides documented; invalid values produce actionable errors; no secrets are stored. **Labels:** `area: config`, `type: feature`, `priority: medium`.

### Produce first freshness report from supplied claims
**Scope:** Run policy evaluation on caller-supplied claim candidates. **Acceptance:** report includes status, policy, evaluation time, and unknown cases; works without an LLM or network. **Labels:** `area: reports`, `type: feature`, `priority: high`.

## 0.2 — Verification providers

### Define provider interface and provenance contract
**Scope:** Specify provider input/output, timeout/error behavior, source metadata, and privacy boundaries. **Acceptance:** contract separates outcome from freshness; providers are opt-in; one ADR records the decision. **Labels:** `area: verification`, `type: research`, `priority: high`.

### Select first verification provider
**Scope:** Compare a small number of source/search options for reliability, license, privacy, cost, and platform constraints. **Acceptance:** documented recommendation and opt-in dependency strategy; no paid resource created. **Labels:** `area: verification`, `type: research`, `priority: medium`.

### Implement one reference verification adapter
**Scope:** Add one provider behind the agreed boundary. **Acceptance:** provider errors are distinct from inconclusive outcomes; provenance is retained; no provider is enabled by default. **Labels:** `area: verification`, `type: feature`, `priority: medium`.

## 0.3 — CLI

### Define CLI commands and exit semantics
**Scope:** Specify `scan`, `verify`, policy inspection, and exit codes based on user workflows. **Acceptance:** help/output examples are consistent; commands do not imply truth certification. **Labels:** `area: cli`, `type: research`, `priority: high`.

### Implement cross-platform scan command
**Scope:** Accept a file or stdin and produce human-readable output. **Acceptance:** Windows/macOS/Linux paths and encoding cases documented; no verification by default; errors have actionable messages. **Labels:** `area: cli`, `type: feature`, `priority: high`.

### Add JSON report output
**Scope:** Serialize the versioned report contract. **Acceptance:** output is deterministic given fixed time/input/policy; schema version is present; unknown states retained. **Labels:** `area: reports`, `type: feature`, `priority: medium`.

### Document privacy and network behavior
**Scope:** Document local processing and all outbound provider calls. **Acceptance:** default scan is offline; opt-in calls are visible; configuration and redaction advice documented. **Labels:** `area: docs`, `type: feature`, `priority: high`.

## 0.4–1.0 — SDK and release maturity

### Stabilize Python SDK surface
**Scope:** Define supported import surface from real usage. **Acceptance:** API docs and compatibility policy exist; CLI is not required to embed core. **Labels:** `area: sdk`, `type: feature`, `priority: medium`.

### Evaluate MCP and agent integration patterns
**Scope:** Assess MCP and Claude Code, Codex, Cursor, Gemini CLI, and OpenCode integration points. **Acceptance:** documented use cases and maintenance cost justify any adapter; no core coupling. **Labels:** `area: integrations`, `type: research`, `priority: low`.

### Design freshness report diff and badge
**Scope:** Explore `factttl diff` and shareable badge semantics. **Acceptance:** status changes and denominator are transparent; unknowns cannot inflate the score; proposal reviewed before implementation. **Labels:** `area: reports`, `type: research`, `priority: low`.

### Define 1.0 compatibility and release policy
**Scope:** Document supported Python versions, public model stability, deprecation, security support, and release cadence. **Acceptance:** policy reviewed and linked from README before 1.0. **Labels:** `area: docs`, `type: research`, `priority: medium`.
