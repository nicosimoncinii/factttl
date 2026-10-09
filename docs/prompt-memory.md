# Local findings used by MCP tools

FactTTL keeps verification observations and user-requested corrections in the
local SQLite file selected with `--verification-db`. The history belongs to the
running FactTTL server. It is not ChatGPT, Claude, or another provider's
permanent memory, and it does not modify model weights.

The native answer tools consult this history before starting a new network
check. Their structured result includes `memory_before_check`, live verification
results, and `required_revisions`. This is the only supported path for giving a
connected model FactTTL memory. The browser extension does not append hidden or
visible blocks to a prompt, intercept a user's Send action, write into the
composer, click Send, or post correction follow-ups.

## What is stored

Records include the narrowly checked property, typed price or stock values,
observation and expiry times, source-relative scope, bounded evidence, and reuse
flags. Expired observations remain history but have
`usable_as_current_fact: false`. A previous contradiction remains visible after
an inconclusive recheck and is not rehabilitated without newer supporting
evidence for the same assertion.

`assertion_supported` refers to the original assertion. A contradictory price
check can still contain a useful observed price while that observation is fresh;
`observed_value_usable_as_current_fact` distinguishes that value. Browser offer
observations do not establish shipping destination, seller selection, technical
compatibility, or checkout total.

Source text and saved claims are untrusted data. They are returned as evidence,
not instructions. A historical user report is labeled as such and is not an
independently verified fact.

## How a later conversation benefits

The later conversation must use the same FactTTL server and have its MCP plugin
available. The model can call `verify_answer`, `verify_recommendations`, or
`recall_content_checks`; the tool result then carries the relevant local history
into that model turn. Tool metadata and server instructions tell the model to
consult history before repeating volatile claims and to revise contradicted
drafts before answering.

The host and model still decide whether to call an available tool. FactTTL
cannot inject memory into an unrelated conversation, force tool use in every
answer, or silently alter a response already produced by the provider. The
browser badges remain useful visual evidence for the user, but displaying a
badge alone does not give the model that evidence.

## Direct context endpoint

The authenticated browser bridge retains `POST /context` as a local read API for
compatible clients. It accepts a bounded query and optional URLs and returns
matching history without web requests. The current browser extension does not
use this endpoint to change outgoing messages. Native model integration uses
the MCP tools documented in [MCP integration](mcp.md).
