# Privacy and network behavior

## Opt-in verification mode

`--enable-verification` enables outbound GET requests to public HTTPS sources
and a local SQLite evidence/correction store. URLs, claims, timestamps, bounded
excerpts and user-requested corrections are persisted under `.factttl` by
default; this directory is ignored by Git. Records remain until you remove the
local store. Requests send URL path/query and standard request headers to the
chosen source; they send no account cookies, API keys or login credentials.
Do not supply credential-bearing URLs. The MCP verification adapter validates
source-anchored semantic assessments supplied by the calling AI. The browser
bridge can additionally call an explicitly configured local Ollama model;
this is a separate opt-in behavior described below. No paid search API is used.

Those requests use the backend fetcher. The optional browser offer reader
described below uses the user's existing Amazon browser session instead.

The private tunnel exposes this one user's store to connected clients. It
provides no per-user isolation inside the server. Use it only in your personal
testing context, on loopback behind the access-controlled tunnel. Production
multi-user hosting requires authentication, tenant isolation and retention
controls. Source excerpts are data, never instructions.

The network-free statements below apply to default freshness mode only.

## Browser news analysis and optional search

The browser bridge accepts text from the enabled chat, obtains public source
pages, and can send a bounded assertion and source excerpt to the configured
Ollama daemon at `127.0.0.1:11434`. No OpenAI API key is used. The project setup
disables Ollama cloud and selects an installed local GGUF model. The local
daemon remains a trusted dependency; FactTTL does not audit other applications
or every connection that daemon could make.

Source discovery is **disabled by default**. Explicitly setting
`FACTTTL_NEWS_DISCOVERY=bing` or using startup `-NewsDiscovery bing` enables
requests to Bing's RSS search endpoint. Bing receives a bounded search query
derived from the selected assertion, a language header, the usual request
headers and the connection IP address. Country is a local context/cache hint;
this adapter does not guarantee region-specific search results. The conversation is not
submitted as the search request, but a query can still reveal sensitive parts
of an assertion. The query filter is not a guarantee that private information
will be removed. Only enable discovery for content you are comfortable sending
to that external service. Bing's retention and service behavior are outside
FactTTL's control.

Search results are candidate URLs, not proof. The tool reads bounded public
HTTPS page bodies through the protected fetcher; it does not treat RSS titles
or snippets as evidence, send account cookies, log in, or bypass CAPTCHA.
Retrieval can fail, and apparently different sources can repeat the same
unverified assertion. A locally generated verdict and quoted source text remain
fallible and source-relative; neither proves universal truth.

The persisted discovery choice is kept in ignored `.factttl/news-model.json`.
Use `-NewsDiscovery disabled` and restart the bridge to disable subsequent
search requests. Already completed requests cannot be recalled from Bing.
Startup `-DisableNews` disables both local news analysis and external discovery,
overriding any previously saved Bing choice; restart an active bridge to apply it.
Turning off FactTTL in a chat removes indicators and cancels queued work;
requests already in progress may have reached their destination.

## Browser product offers and prompt memory

For an Amazon product link in an enabled chat, the extension can open an
inactive product tab, read the rendered primary offer and close that tab.
The browser uses its normal session and selected marketplace. The reader
collects only the product title, ASIN, URL, displayed price/currency,
availability and any displayed reference price. These fields go to the
authenticated local bridge. It does not collect addresses or account details,
purchase anything, select a different seller or bypass CAPTCHA. Amazon host
permissions are limited to the six supported marketplaces. Public backend
fetching remains a fallback when the browser cannot read the offer.

With the separate memory switch enabled, an explicit user Send or plain Enter
looks up relevant stored checks locally. The extension adds a visible, quoted
FactTTL block to that same outgoing message. The selected chat provider thus
receives the relevant assertion, observed value, source URL, status and
expiry along with the user's message. The lookup itself contacts only the
local bridge. This memory-only path resumes the user's send action.

The separate **Correzione automatica** switch authorizes visible correction
follow-ups after a completed response. The selected provider receives original
URLs/assertions, typed observed stock/price/discount values and, for grounded
news contradictions, up to two short quoted source passages per finding.
The extension asks the model to acknowledge the incorrect indication and
provide replacements respecting the original request. The choice is saved per
chat. A local hash ledger avoids duplicate sends; at most two follow-ups are
attempted for each user request. No full chat transcript, source HTML, cookies,
credentials or API keys are added to that follow-up. The original answer is
preserved and a FactTTL correction card is appended below it.

Turning memory or FactTTL off removes an unsent block owned by
FactTTL; if that block was edited and cannot be removed safely, sending is
blocked with an explanation. The extension does not alter the provider's
model weights or permanent memory. See [prompt memory](prompt-memory.md).

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
network requests in its default freshness mode. The optional verification
components described above add public fetching, limited extraction, local
analysis and persistence; they are not part of the network-free core evaluator.

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
