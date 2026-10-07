"""Tests for the optional MCP tool adapter."""

from __future__ import annotations

import asyncio
import sys
from typing import cast

import pytest
from mcp import Client, StdioServerParameters

from factttl.config import parse_policy_toml
from factttl.mcp_server import create_server, evaluate_fact_freshness

POLICY = parse_policy_toml(
    """
schema_version = 1
[categories.release]
ttl = "7d"
[categories.archive]
review_disabled = true
"""
)


def test_tool_returns_structured_freshness_without_verification_claim() -> None:
    result = evaluate_fact_freshness(
        policy_config=POLICY,
        category="release",
        temporal_class="TIME_SENSITIVE",
        last_checked_at="2026-09-30T12:00:00+02:00",
        evaluation_time="2026-10-06T12:00:00Z",
    )
    policy = cast(dict[str, object], result["policy"])

    assert result["status"] == "FRESH"
    assert result["evaluation_time"] == "2026-10-06T12:00:00.000000Z"
    assert result["last_checked_at"] == "2026-09-30T10:00:00.000000Z"
    assert result["review_due_at"] == "2026-10-07T10:00:00.000000Z"
    assert policy["resolved_ttl_seconds"] == 604800
    scope = result["scope"]
    assert isinstance(scope, str)
    assert "no fact verification performed" in scope


def test_claim_override_has_precedence_over_category_disable() -> None:
    result = evaluate_fact_freshness(
        policy_config=POLICY,
        category="archive",
        temporal_class="UNKNOWN",
        last_checked_at=None,
        evaluation_time="2026-10-06T12:00:00Z",
        ttl_seconds=0,
    )
    policy = cast(dict[str, object], result["policy"])

    assert result["status"] == "UNVERIFIED"
    assert policy["resolved_ttl_seconds"] == 0
    assert policy["review_disabled"] is False


def test_category_disable_is_reported_as_not_required() -> None:
    result = evaluate_fact_freshness(
        policy_config=POLICY,
        category="archive",
        temporal_class="TIME_SENSITIVE",
        last_checked_at="2026-10-01T00:00:00Z",
        evaluation_time="2026-10-06T12:00:00Z",
    )
    policy = cast(dict[str, object], result["policy"])

    assert result["status"] == "NOT_REQUIRED"
    assert policy["review_disabled"] is True
    assert result["last_checked_at"] is None


@pytest.mark.parametrize(
    ("updates", "error"),
    [
        ({"evaluation_time": "2026-10-06T12:00:00"}, "timezone"),
        ({"last_checked_at": "yesterday"}, "ISO 8601"),
        ({"ttl_seconds": -1}, "non-negative"),
        ({"ttl_seconds": 1, "review_disabled": True}, "mutually exclusive"),
        ({"temporal_class": "DYNAMIC"}, "temporal_class must be one of"),
        ({"category": "x" * 129}, "at most 128 characters"),
        ({"evaluation_time": "2" * 65}, "at most 64 characters"),
    ],
)
def test_rejects_invalid_tool_inputs(updates: dict[str, object], error: str) -> None:
    arguments: dict[str, object] = {
        "policy_config": POLICY,
        "category": None,
        "temporal_class": None,
        "last_checked_at": None,
        "evaluation_time": "2026-10-06T12:00:00Z",
    }
    arguments.update(updates)
    with pytest.raises((TypeError, ValueError), match=error):
        evaluate_fact_freshness(**arguments)  # type: ignore[arg-type]


def test_server_registers_expected_tool_name() -> None:
    server = create_server(POLICY)
    tools = asyncio.run(server.list_tools())
    assert [tool.name for tool in tools] == ["evaluate_fact_freshness"]
    tool = tools[0]
    assert tool.annotations is not None
    assert tool.annotations.read_only_hint is True
    assert tool.annotations.destructive_hint is False
    assert tool.annotations.idempotent_hint is True
    assert tool.annotations.open_world_hint is False
    assert tool.output_schema is not None


def test_stdio_mcp_client_can_call_freshness_tool() -> None:
    async def call_tool() -> dict[str, object]:
        async with Client(
            StdioServerParameters(
                command=sys.executable,
                args=["-m", "factttl.mcp_server"],
            )
        ) as client:
            response = await client.call_tool(
                "evaluate_fact_freshness",
                {
                    "evaluation_time": "2026-10-06T12:00:00Z",
                    "last_checked_at": "2026-10-06T10:00:00Z",
                    "ttl_seconds": 3600,
                },
            )
            assert response.structured_content is not None
            return cast(dict[str, object], response.structured_content)

    result = asyncio.run(call_tool())
    assert result["status"] == "STALE"
