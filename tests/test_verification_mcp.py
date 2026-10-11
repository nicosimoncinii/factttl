"""Public MCP contracts for opt-in checks and cross-chat correction memory."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import pytest
from mcp.types import CallToolResult

from factttl.config import PolicyConfig
from factttl.mcp_server import create_server
from factttl.verification import VerificationResult


def _native_analysis(text: str, links: list[str]) -> dict[str, object]:
    return {
        "status": "CONTRADICTED",
        "checks": [
            {
                "assertion_scope": "current unit price",
                "regional_context": {"country": "IT", "language": "it"},
                "result": {
                    "url": links[0],
                    "kind": "product_price",
                    "outcome": "CONTRADICTED",
                    "claim_text": text,
                    "expected_value": "9.99 EUR",
                    "observed_value": "12.99 EUR",
                    "observed_at": datetime.now(UTC).isoformat(),
                    "evidence": [{"provider": "test_fixture", "value": "12.99"}],
                },
            }
        ],
        "unchecked_claims": [],
        "prior_corrections": [],
    }


def test_opt_in_tools_and_permissions(tmp_path: Path) -> None:
    server = create_server(PolicyConfig({}), tmp_path / "checks.sqlite3")
    tools = {tool.name: tool for tool in asyncio.run(server.list_tools())}
    assert server.instructions is not None
    assert (
        "connection errors do not mean a product is out of stock" in server.instructions
    )
    assert "never invent tool calls" in server.instructions
    assert set(tools) == {
        "evaluate_fact_freshness",
        "inspect_live_source",
        "verify_content",
        "assess_claim_with_live_evidence",
        "recall_content_checks",
        "report_content_correction",
        "verify_answer",
        "verify_recommendations",
        "submit_answer_verification",
        "get_answer_verification",
    }
    for name in ("verify_content", "assess_claim_with_live_evidence"):
        annotations = tools[name].annotations
        assert annotations is not None
        assert annotations.read_only_hint is False
        assert annotations.open_world_hint is True
        assert annotations.destructive_hint is False
    annotations = tools["recall_content_checks"].annotations
    assert annotations is not None and annotations.read_only_hint is True
    annotations = tools["report_content_correction"].annotations
    assert annotations is not None and annotations.open_world_hint is False
    assert server.instructions and "does not alter model weights" in server.instructions


def test_correction_can_be_recalled_by_another_server(tmp_path: Path) -> None:
    database = tmp_path / "checks.sqlite3"

    async def exercise() -> dict[str, object]:
        writer = create_server(PolicyConfig({}), database)
        written = await writer.call_tool(
            "report_content_correction",
            {
                "url": "https://example.com/esp32",
                "claim_text": "ESP32 disponibile in offerta",
                "correction": "L'utente segnala che non è disponibile né scontato",
            },
        )
        assert isinstance(written, CallToolResult)
        reader = create_server(PolicyConfig({}), database)
        recalled = await reader.call_tool("recall_content_checks", {"query": "ESP32"})
        assert isinstance(recalled, CallToolResult)
        return cast(dict[str, object], recalled.structured_content)

    result = asyncio.run(exercise())
    claims = cast(list[dict[str, object]], result["claims"])
    assert len(claims) == 1
    assert claims[0]["do_not_reuse_prior_assertion"] is True
    assert claims[0]["usable_as_current_fact"] is False
    assert claims[0]["independently_verified"] is False


def test_verify_answer_returns_native_revisions_without_a_chat_prompt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "factttl.mcp_verification.verify_message",
        lambda text, links, store, preferences, cancellation_event: _native_analysis(
            text, links
        ),
    )

    async def exercise() -> dict[str, object]:
        server = create_server(PolicyConfig({}), tmp_path / "checks.sqlite3")
        response = await server.call_tool(
            "verify_answer",
            {
                "text": "ESP32 costa 9.99 EUR https://example.com/esp32",
                "country": "IT",
                "language": "it",
            },
        )
        assert isinstance(response, CallToolResult)
        return cast(dict[str, object], response.structured_content)

    envelope = asyncio.run(exercise())
    assert envelope["status"] == "COMPLETED"
    result = cast(dict[str, object], envelope["result"])
    assert result["interaction_mode"] == "native_mcp_tool_result"
    assert result["provider_memory_or_weights_modified"] is False
    revisions = cast(list[dict[str, object]], result["required_revisions"])
    assert revisions[0]["action"] == "update_price_and_recalculate_total"
    assert revisions[0]["observed_value"] == "12.99 EUR"
    assert "prompt" not in result


def test_verify_recommendations_preserves_quantity_and_price_fields(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "factttl.mcp_verification.verify_message",
        lambda text, links, store, preferences, cancellation_event: _native_analysis(
            text, links
        ),
    )

    async def exercise() -> dict[str, object]:
        server = create_server(PolicyConfig({}), tmp_path / "checks.sqlite3")
        response = await server.call_tool(
            "verify_recommendations",
            {
                "items": [
                    {
                        "name": "ESP32 DevKit",
                        "url": "https://example.com/esp32",
                        "quantity": 2,
                        "expected_unit_price_eur": "9.99",
                    }
                ],
                "country": "IT",
                "language": "it",
            },
        )
        assert isinstance(response, CallToolResult)
        return cast(dict[str, object], response.structured_content)

    envelope = asyncio.run(exercise())
    assert envelope["status"] == "COMPLETED"
    result = cast(dict[str, object], envelope["result"])
    requested = cast(list[dict[str, object]], result["requested_items"])
    assert requested == [
        {
            "name": "ESP32 DevKit",
            "url": "https://example.com/esp32",
            "quantity": 2,
            "expected_unit_price_eur": "9.99",
        }
    ]
    assert result["cart_total_verified"] is False
    assert result["compatibility_verified"] is False


def test_live_check_persists_outcome(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def check(
        url: str, kind: str, expected_value: str | None, claim_text: str | None
    ) -> VerificationResult:
        return VerificationResult(
            url=url,
            kind=kind,
            outcome="CONTRADICTED",
            observed_at=datetime.now(UTC).isoformat(),
            rationale="Price changed to 25 EUR",
            expected_value=expected_value,
            claim_text=claim_text,
            observed_value="25 EUR",
            evidence=[{"provider": "live_public_web", "field": "price", "value": "25"}],
        )

    monkeypatch.setattr("factttl.web_verifier.verify_url", check)

    async def exercise() -> dict[str, object]:
        server = create_server(PolicyConfig({}), tmp_path / "checks.sqlite3")
        result = await server.call_tool(
            "verify_content",
            {
                "url": "https://example.com/esp32",
                "kind": "product_price",
                "expected_value": "19.99 EUR",
            },
        )
        assert isinstance(result, CallToolResult)
        return cast(dict[str, object], result.structured_content)

    result = asyncio.run(exercise())
    assert result["history_count"] == 1
    assert result["do_not_reuse_prior_assertion"] is True


def test_new_source_can_reassess_original_corrected_reference(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    subject = "https://original.example/article"
    source = "https://primary.example/update"
    claim = "Example entity holds position X"

    def assessment(
        url: str, claim_text: str, evidence_quote: str, outcome: str, rationale: str
    ) -> VerificationResult:
        return VerificationResult(
            url=url,
            kind="claim",
            claim_text=claim_text,
            outcome=outcome,
            observed_at=datetime.now(UTC).isoformat(),
            rationale=rationale,
            evidence=[
                {
                    "provider": "ai_assessed_live_source",
                    "url": url,
                    "quote": evidence_quote,
                }
            ],
        )

    monkeypatch.setattr("factttl.web_verifier.verify_claim_evidence", assessment)

    async def exercise() -> dict[str, object]:
        server = create_server(PolicyConfig({}), tmp_path / "checks.sqlite3")
        await server.call_tool(
            "report_content_correction",
            {
                "url": subject,
                "claim_text": claim,
                "correction": "User disputes this",
            },
        )
        await server.call_tool(
            "assess_claim_with_live_evidence",
            {
                "url": source,
                "subject_url": subject,
                "claim_text": claim,
                "evidence_quote": "Current source statement",
                "outcome": "SUPPORTED",
                "rationale": "Caller compares the same entity and date with evidence",
            },
        )
        result = await server.call_tool("recall_content_checks", {"url": subject})
        assert isinstance(result, CallToolResult)
        return cast(dict[str, object], result.structured_content)

    result = asyncio.run(exercise())
    claims = cast(list[dict[str, object]], result["claims"])
    assert len(claims) == 1
    assert claims[0]["history_count"] == 2
    assert claims[0]["do_not_reuse_prior_assertion"] is False
    assert claims[0]["independently_verified"] is False
    observed = cast(dict[str, object], claims[0]["result"])
    assert observed["url"] == subject
    evidence = cast(list[dict[str, object]], observed["evidence"])
    assert evidence[0]["url"] == source
