# Roadmap

This roadmap describes intended increments, not shipped capabilities or fixed dates. Each milestone should end with a review of scope and usability before the next is started.

## 0.1 — Freshness foundation

- Agree on claim, policy, and status semantics.
- Accept text and structured claim candidates through a small local interface.
- Classify temporal sensitivity and category with explicit uncertainty.
- Apply configurable TTL policies at a supplied evaluation time.
- Produce a report that separates freshness from truth and evidence quality.

## 0.2 — Verification provider contract

- Define an optional provider interface and provenance requirements.
- Add one narrow reference adapter only after source selection criteria are documented.
- Keep verification opt-in; do not verify stable claims by default.

## 0.3 — CLI

- Add cross-platform `scan`, policy inspection, and report output.
- Provide JSON output for automation and concise text output for people.
- Make unsupported extraction cases visible.

## 0.4 — Python SDK

- Stabilize import paths and versioned public data contracts based on V0.1 use.
- Document embedding the core without a CLI or network provider.

## 0.5 — Integration layer

- Evaluate MCP and agent-tool integration based on demonstrated demand.
- Explore Claude Code, Codex, Cursor, Gemini CLI, and OpenCode workflows.
- Consider REST only if process-boundary use cases justify a server.
- Consider a JavaScript SDK only if a clear, maintainable use case exists.

## 1.0 — Stable freshness engine

- Freeze and document core freshness semantics and compatibility policy.
- Publish supported extraction/provider contracts and limitations.
- Establish release, security, and support practices.

## Later ideas

- `factttl diff`: compare reports and show claims whose freshness status changed.
- Freshness summary/badge: a transparent roll-up with counts, denominator, evaluation time, and policy context. A single percentage must never hide unknown or unclassified claims.
- Additional category packs and integration adapters, maintained independently where practical.
