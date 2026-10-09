# MCP integration

## Native answer checks and local memory

Add `--enable-verification` to enable the native answer workflow as well as the
lower-level source and history tools. The primary tools are:

| Tool | Purpose |
|---|---|
| `verify_answer` | Check a draft containing current news, direct product links, prices, stock or discounts. |
| `verify_recommendations` | Check structured recommendation rows while preserving name, quantity and an optional asserted unit price. |
| `submit_answer_verification` | Start the same answer check without waiting for slow local inference. |
| `get_answer_verification` | Poll a submitted job until its real result is complete. |

Their structured results include earlier relevant SQLite findings before the
new check, property-level evidence, and `required_revisions`. Evidence reaches
the model as an MCP tool result. No FactTTL component writes a prompt into the
user's composer, clicks Send, or posts a correction message.

The lower-level `inspect_live_source`, `verify_content`,
`assess_claim_with_live_evidence`, `recall_content_checks` and
`report_content_correction` tools remain available for focused work. They fetch
public HTTPS sources and/or persist local evidence and corrections, with
annotations matching their behavior. The default remains the single offline
tool described below. See [verification and memory](verification-model.md) for
inputs, outcomes, reuse rules and limitations.

For the personal ChatGPT tunnel configuration:

```powershell
factttl-mcp --transport streamable-http --enable-verification --verification-db .factttl/verification.sqlite3
```

After restarting the server, refresh the plugin's tools in ChatGPT and start a
new chat with FactTTL selected. For a product list, the model should build
candidate rows, call `verify_recommendations`, revise contradicted items, verify
direct replacements, and only then answer. If the result is `RUNNING`, it must
poll `get_answer_verification`; a job ID is not a verdict.

Persistent memory is in the server's SQLite file. The host and model decide
whether to call an available tool, so connection and good metadata improve tool
selection but do not guarantee invocation in every answer or unrelated chat.
FactTTL cannot modify model weights or provider memory.

## Default offline mode

FactTTL provides an optional Model Context Protocol (MCP) server with one
read-only tool, `evaluate_fact_freshness`. The tool evaluates freshness from
timestamps and policy supplied by the caller. It does not receive claim text,
verify whether a fact is true, fetch evidence, use an LLM, or initiate outbound
network requests. Its structured response reports the status, effective TTL or
disable setting, input timestamps, due time, and rationale.

The evaluator is deterministic: callers must supply `evaluation_time`. Timestamps
must be ISO 8601 strings with a timezone, such as `2026-10-06T12:00:00Z`.
The optional `ttl_seconds` and `review_disabled` parameters are per-claim
overrides and are mutually exclusive. Resolution follows the normal FactTTL
order: per-claim override, category policy, then the `STABLE` class default.
The tool is annotated as read-only and closed-world; those MCP annotations are
client-facing hints, while the implementation performs no writes or external
calls. A supplied `last_checked_at` is caller-provided assessment metadata:
FactTTL does not authenticate or verify its origin.
Category names are limited to 128 characters and timestamps to 64 characters
to bound individual tool inputs. The CLI separately caps input documents at
10 MiB.

## Local stdio client

From a FactTTL checkout, install the optional MCP extra:

```powershell
uv sync --extra mcp
```

After FactTTL is published to a package index, the equivalent install is
`uv pip install "factttl[mcp]"`.

Configure an MCP host that supports local stdio servers to launch
`factttl-mcp` as a subprocess. Example JSON configuration:

```json
{
  "mcpServers": {
    "factttl": {
      "command": "factttl-mcp",
      "args": ["--policy", "C:/Users/you/factttl.toml"]
    }
  }
}
```

Use an absolute path for the policy file. The policy is loaded once at server
startup; restart the MCP server after changing it. Without `--policy`, only
per-call overrides and the `STABLE` fallback apply.

## HTTP and remote clients

For a local HTTP client with live answer tools, start:

```powershell
factttl-mcp --transport streamable-http --enable-verification --verification-db .factttl/verification.sqlite3
```

It listens on `127.0.0.1:8000` by default, with the MCP endpoint at
`http://127.0.0.1:8000/mcp`. ChatGPT cannot reach this loopback address directly.
A ChatGPT connection requires a compatible HTTPS endpoint or Secure MCP Tunnel
plus the permissions of the current account/workspace. Starting the local
server proves only local readiness; it does not prove that the tunnel is
authenticated, the plugin is installed, or the active chat has selected it.
Follow the [personal connection test](chatgpt-local-test.md) and OpenAI's current
[connection guide](https://developers.openai.com/plugins/deploy/connect-chatgpt).

Do not expose the server's unauthenticated HTTP endpoint to the public
internet. For remote use, deploy behind an authenticated HTTPS MCP gateway or
use a private, access-controlled tunnel that enforces authentication. Binding
to another interface with `--host` does not add authentication or TLS.

The default freshness tool does not call the network. The answer and live-source
tools enabled by `--enable-verification` do make bounded public requests and can
write the SQLite history. Review the host, firewall, tunnel, authentication,
logging, source requests, and database access before enabling remote use.
