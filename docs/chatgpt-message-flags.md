# Passive status buttons in ChatGPT (personal test)

This browser extension adds a switch for each conversation and a status button
next to each external HTTPS link and below uncovered paragraphs in completed
assistant responses. It supports desktop Firefox, Chrome and Edge;
an MCP plugin alone cannot add badges to every native message.
The extension is not installed inside Codex's internal browser or the ChatGPT
desktop application.

## Behavior

- Chats start disabled. Enable the switch to check existing and new responses.
- The extension waits for the answer to finish, preserves each link's original
  position and submits the text to the local authenticated bridge.
- A supported check is green, a conflicting check red, and partial or
  inconclusive evidence amber. Messages without applicable checks remain gray.
- Evidence, source, check time and limitations appear only when opening a badge.
- Disable the switch to hide all badges and cancel queued work. A source request
  already on the network may finish; completed observations already saved remain
  in the store. Cancellation is checked before further requests and writes.
- Switching chats never moves a previous answer's result onto a different answer.
- Checks are refreshed after five minutes while the chat is visible and enabled.

## What the browser checks automatically

The scanner recognizes explicitly URL-associated prices in EUR, product stock,
discount assertions and link accessibility. Amazon ASIN links also request stock
and an observed public price even when the answer gives no explicit price.
ChatGPT product-search shortcuts (`/?hints=search&q=...`) and Amazon search
pages receive a structural search badge: no offer is selected. This local check
does not open a private ChatGPT page or require the bridge. Product images and
favicon assets are excluded from merchant checks. Search links request a direct
offer in the requested store, even when the bridge is unavailable; this does
not establish that a product is out of stock or that its quoted price is false.
Selected country and language are user preferences, not GPS or delivery proof.
The source request uses the selected language and flags a different marketplace.
It preserves conditional language,
questions, historical prices, quoted statements, mixed product references and
other prose as unchecked. It checks at most six properties per message, with
three source requests in parallel. It leaves additional properties unchecked.

An HTTP 200 is evidence of link accessibility only. It does not prove product
availability, price, discount, a news story or the entire answer. A green message
badge requires support for all recognized checks and no uncovered prose or
unresolved prior corrections. In practice many useful answers are partially
checked. News pages expose title, readable excerpt and publication age, kept
separate from truth. An optional installed local Ollama model can compare the
URL-associated assertion with the fetched source; definitive results require
validated quotations. The UI calls this source consistency, not independent
confirmation. Without a configured model, the news remains unverified.
Optional public Bing discovery finds candidate sources for recognized news
assertions without a URL; domain diversity does not establish independence.

The local verifier stores evidence and prior corrections across chats. Prior
corrections prevent an unqualified green status. The extension does not read
ChatGPT's private conversation APIs, change model weights, or transmit prompts
to the model. It never intercepts a user send, modifies the composer, clicks
Send, or posts correction follow-ups. Its result is a visual explanation for
the person reading the page.

For the model to receive evidence and revise a draft, connect and select the
separate FactTTL MCP plugin. Native tools return structured evidence directly
to the model and can recall the same local SQLite history. The host and model
decide whether to call them; the browser switch cannot force tool selection.
See [local findings used by MCP tools](prompt-memory.md).

A separately selected FactTTL plugin has its own tool availability and is not
disabled by the browser switch.
The settings connection status describes only the browser extension and its
local bridge (`8765`). It does not assert that an optional ChatGPT MCP app or
tunnel is connected; those are separate processes and need separate readiness
checks. See [the personal MCP guide](chatgpt-local-test.md).

## Distribution

The dedicated Firefox folder has a Firefox-specific manifest; reload it in
`about:debugging` after a local update, then reload the ChatGPT tab. Generated
unsigned packages are development artifacts. Normal permanent installation
requires Mozilla signing and a published or signed self-distributed extension.
See the [distribution plan](../integrations/chatgpt-extension/DISTRIBUTION.md).

## Local transport and privacy

The extension can send data only to `http://127.0.0.1:8765`. The bridge requires a
private bearer token, an exact extension origin and the loopback Host header.
Its generated `.factttl/extension-config.json` is ignored by Git. Import it in
the extension options; do not share it. Tokens are kept in trusted extension
storage and never passed to the page or content script.

For slow sources the extension starts a bounded asynchronous job, polls it and
can cancel it. Job identifiers are random; completed jobs expire after five
minutes. The bridge accepts at most four unfinished jobs and runs two at once.
Entire message text is transient job input; the SQLite store retains only the
derived checks, associated excerpts and provenance. Source requests are public,
anonymous HTTPS requests, without the user's ChatGPT or shopping-site cookies.

Read [installation steps](../integrations/chatgpt-extension/README.md). On this
Windows checkout, `scripts/Start-FactTTL-Browser.ps1` starts the bridge hidden
and reports only configuration paths, without printing its token.

`integrations/chatgpt-extension/demo.html` is a separate local UI fixture. It is
not loaded by the extension's manifest and does not install the extension.
