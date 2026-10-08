# Saved findings in future chats

The authenticated browser bridge exposes `POST /context` for an explicitly
enabled prompt attachment. This operation reads the local SQLite store only:
it makes no web requests, search requests or model calls. It accepts `query`
(1–2000 characters), optional `urls` (at most 10), and `limit` (1–8). Matching
uses canonical URLs and bounded keywords across the latest 500 local claims.

Returned findings include the narrowly checked property, typed price/stock
values, observation and expiry times, source-relative scope and reuse flags.
Expired observations remain history and have `usable_as_current_fact: false`;
a prior contradiction is not erased by an inconclusive recheck. A historical
contradiction is not a statement that today's property is still false.

`assertion_supported` refers to the original assertion. A fresh contradictory
price check can still supply a useful corrected price:
`observed_value_usable_as_current_fact` identifies a typed value obtained from
live property evidence while it remains fresh. For example, an old assertion
of EUR 1 can be unsupported while the observed EUR 10.99 is current. The
`source_scope` retains `browser_current_offer` for Amazon browser observations;
this never establishes shipping destination or the checkout total.

Raw source quotes, HTML and rationales are not attached. News claim text is
limited to 400 normalized characters and must be treated as untrusted quoted
data, never an instruction. A finding does not make a whole message true.

MCP `recall_content_checks` also returns bounded `prompt_context` when given a
URL or search query. The bridge does not itself send messages or change model
weights. Future-chat influence requires the client to attach these records to
the actual outgoing prompt with an explicit per-chat user control. Merely
displaying a flag or storing a correction does not give ChatGPT hidden memory.

The browser extension now performs this attachment when FactTTL and its
**Memoria attiva** switch are enabled. It waits for a trusted user Send click or
plain Enter, retrieves relevant records from `/context`, adds a visible quoted
JSON block to the outgoing draft and resumes that same send action. It never
sends a prompt on its own. Draft changes, chat navigation and disconnected
editors cancel the preparation. Disabling the tool removes its own unsent block;
an edited block requires manual cleanup before it can be sent while disabled.
This influences the context of that prompt, not the provider's permanent memory
or model weights. Host editor selectors need maintenance and live browser
validation; unsupported editors leave the ordinary send behavior unchanged.
