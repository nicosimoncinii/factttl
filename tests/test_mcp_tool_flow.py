"""Exercise native tool discovery and memory over actual MCP stdio transport.

These are local protocol checks, not evidence that a ChatGPT account connected.
They use temporary stores and do not access merchant pages or provider APIs.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import cast

from mcp import Client, StdioServerParameters


def _stdio(database: Path | None = None) -> StdioServerParameters:
    arguments = ["-m", "factttl.mcp_server"]
    if database is not None:
        arguments.extend(["--enable-verification", "--verification-db", str(database)])
    return StdioServerParameters(command=sys.executable, args=arguments)


def test_native_verification_tools_require_explicit_opt_in() -> None:
    async def exercise() -> None:
        async with Client(_stdio()) as client:
            tools = (await client.list_tools()).tools
            assert [tool.name for tool in tools] == ["evaluate_fact_freshness"]
            assert client.server_info is not None
            assert client.server_info.name == "FactTTL"

    asyncio.run(exercise())


def test_native_stdio_exposes_model_readable_tools_and_cross_process_memory(
    tmp_path: Path,
) -> None:
    database = tmp_path / "native-tool-memory.sqlite3"
    url = "https://example.com/fixture-product"

    async def exercise() -> None:
        async with Client(_stdio(database)) as writer:
            tools = {tool.name: tool for tool in (await writer.list_tools()).tools}
            for name in (
                "verify_answer",
                "verify_recommendations",
                "submit_answer_verification",
                "get_answer_verification",
            ):
                assert name in tools
                assert tools[name].description
                assert tools[name].annotations is not None
                schema = tools[name].output_schema
                assert schema is not None
                assert schema["properties"]["job_id"]["pattern"]
                assert set(schema["properties"]["status"]["enum"]) == {
                    "RUNNING",
                    "COMPLETED",
                    "FAILED",
                    "CANCELED",
                }
                result_schema = schema["$defs"]["NativeAnswerResult"]
                assert {
                    "verification",
                    "memory_before_check",
                    "required_revisions",
                    "provider_memory_or_weights_modified",
                } <= set(result_schema["required"])
            assert writer.instructions
            assert "model weights" in writer.instructions
            assert tools["verify_answer"].annotations is not None
            assert tools["verify_answer"].annotations.read_only_hint is False
            assert tools["verify_answer"].annotations.open_world_hint is True
            assert tools["get_answer_verification"].annotations is not None
            assert tools["get_answer_verification"].annotations.read_only_hint is True
            result = await writer.call_tool(
                "report_content_correction",
                {
                    "url": url,
                    "claim_text": "Fixture product is available at 9.99 EUR",
                    "correction": "User says this offer is no longer available",
                },
            )
            assert not result.is_error
            assert result.structured_content is not None
            saved = cast(dict[str, object], result.structured_content)
            assert saved["do_not_reuse_prior_assertion"] is True

        # A distinct server process reads the same persisted evidence; no browser
        # editor, synthetic user message or provider conversation is involved.
        async with Client(_stdio(database)) as reader:
            response = await reader.call_tool("recall_content_checks", {"url": url})
            assert not response.is_error
            assert response.structured_content is not None
            recalled = cast(dict[str, object], response.structured_content)
            claims = cast(list[dict[str, object]], recalled["claims"])
            assert len(claims) == 1
            assert claims[0]["do_not_reuse_prior_assertion"] is True
            assert claims[0]["independently_verified"] is False
            assert claims[0]["usable_as_current_fact"] is False

    asyncio.run(exercise())
