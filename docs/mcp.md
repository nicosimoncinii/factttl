# MCP integration

## Optional live checks and memory

Add `--enable-verification` to enable `inspect_live_source`, `verify_content`,
`assess_claim_with_live_evidence`, `recall_content_checks` and
`report_content_correction`. These tools fetch public HTTPS sources and/or
persist local evidence and corrections, with write/open-world annotations
matching their behavior. The default remains the single offline tool described
below. See [verification and memory](verification-model.md) for inputs, outcomes,
reuse rules and limitations.

For the personal ChatGPT tunnel configuration:

```powershell
factttl-mcp --transport streamable-http --enable-verification --verification-db .factttl/verification.sqlite3
```

After restarting the server, refresh the plugin's tools in ChatGPT and start a
new chat with FactTTL selected. Ask it to check a source before recommending it
and consult earlier corrections. Persistent memory is in the server's SQLite
file; it does not give the plugin control over unrelated chats.

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

For a local HTTP client, start:

```powershell
factttl-mcp --transport streamable-http
```

It listens on `127.0.0.1:8000` by default, with the MCP endpoint at
`http://127.0.0.1:8000/mcp`. HTTP transport is useful only when the client can
reach that endpoint. ChatGPT cannot launch or connect directly to a local
stdio subprocess. A ChatGPT MCP connection requires a compatible remote HTTPS
endpoint that ChatGPT can reach, with the authentication and deployment
requirements of the current ChatGPT plan/workspace. Those availability and
configuration options can change; check the [current OpenAI developer-mode and
MCP app guide](https://help.openai.com/en/articles/12584461-developer-mode-and-full-mcp-connectors-in-chatgpt)
before setting up a connection.

Do not expose the server's unauthenticated HTTP endpoint to the public
internet. For remote use, deploy behind an authenticated HTTPS MCP gateway or
use a private, access-controlled tunnel that enforces authentication. Binding
to another interface with `--host` does not add authentication or TLS.

FactTTL's MCP adapter itself does not call the network, but the HTTP transport
accepts network requests from clients that can reach its bind address. Review
the host, firewall, tunnel, authentication, logging, and policy-file access
before enabling remote access.
