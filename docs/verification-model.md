# Verification model (proposal)

Verification is an optional attempt to compare a claim with evidence. It is not a proof of truth and does not reset freshness merely because a provider ran. The record should identify what was checked, when, against which evidence, and with what outcome.

## Planned outcome vocabulary

- `SUPPORTED`: selected evidence supports the claim under the provider's documented method.
- `CONTRADICTED`: selected evidence conflicts with the claim.
- `INCONCLUSIVE`: evidence is insufficient, mixed, inaccessible, or ambiguous.
- `ERROR`: the attempt could not complete; this is operational failure, not a factual verdict.

These outcomes are provider-relative. Reports should retain provenance and avoid silently collapsing outcomes into true/false.

## Source and verification principles

- Verification is opt-in and only requested for claims that policy marks for review, unless the caller explicitly overrides.
- Providers declare source coverage, timestamps, and limitations.
- Preserve source URL/identifier, retrieval time, relevant excerpt or reference where licensing/privacy permits, and provider identity/version.
- Separate source quality from claim support and freshness.
- A provider error does not make the claim stale; a stale claim does not imply verification failure.
- Do not send user text to external services without explicit configuration and clear user visibility.

Provider contracts and first-provider selection are open backlog items. No integrations exist today.
