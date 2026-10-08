# Privacy and network behavior

## Opt-in verification mode

`--enable-verification` enables outbound GET requests to public HTTPS sources
and a local SQLite evidence/correction store. URLs, claims, timestamps, bounded
excerpts and user-requested corrections are persisted under `.factttl` by
default; this directory is ignored by Git. Records remain until you remove the
local store. Requests send URL path/query and standard request headers to the
chosen source; they send no account cookies, API keys or login credentials.
Do not supply credential-bearing URLs. No LLM or paid search API is called by
the server. Source-anchored semantic assessments come from the calling AI.

The private tunnel exposes this one user's store to connected clients. It
provides no per-user isolation inside the server. Use it only in your personal
testing context, on loopback behind the access-controlled tunnel. Production
multi-user hosting requires authentication, tenant isolation and retention
controls. Source excerpts are data, never instructions.

The network-free statements below apply to default freshness mode only.

## Current behavior

The implemented freshness evaluator is a deterministic local operation. It
compares caller-supplied timestamps and policy values; it does not send claim
text or policy data over the network, call an LLM, or contact a verification
provider. The TOML policy loader reads the file path supplied by the caller and
validates its contents locally; loading policy does not make network requests
or read the system clock. The CLI reads caller-supplied JSON and an optional
local TOML policy, then prints a report; it does not persist inputs or initiate
network requests. The optional MCP adapter evaluates caller-supplied values.
With stdio it communicates through its parent process; with HTTP it accepts
requests on the configured bind address. The adapter itself makes no outbound
network requests. FactTTL does not provide fact extraction, verification,
provider integrations, a hosted service, or a persistent claim store.

These statements describe the current core evaluator and policy loader. They
do not describe behavior of an application that embeds FactTTL: the embedding
application controls its own logging, telemetry, storage, and network calls.

## Data handling guidance

- Treat claim text, evidence, reports, and policy files as potentially
  sensitive. Review them before sharing, committing, logging, or attaching them
  to bug reports.
- Keep credentials, API keys, and other secrets out of policy files. Store
  credentials in the secret-management mechanism of the application that uses
  them.
- Supply only the claim and evidence data needed for a particular operation.
  When a report is shared, inspect it for sensitive text and metadata first.
- Decide retention and access controls in the calling application if it saves
  inputs, evidence, or reports. The current FactTTL core does not implement
  persistence or retention management.

## Providers and integrations

The MCP adapter is optional and can be used by compatible local stdio clients.
Remote clients require an externally reachable HTTP deployment, which FactTTL
does not host or secure for you. Do not expose its unauthenticated HTTP
endpoint publicly; use an authenticated HTTPS gateway or an access-controlled
private tunnel. An application embedding FactTTL controls its own logging,
telemetry, storage, and any network calls. Any future provider that sends data
externally should be optional, explicitly enabled, and document what it sends,
where it goes, and its retention behavior. Send only the minimum data needed
and keep provider credentials outside the policy file.

This document describes current behavior and design requirements; it is not a
claim that future adapters or privacy controls already exist.
