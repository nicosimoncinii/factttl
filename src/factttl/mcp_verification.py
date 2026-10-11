"""Native MCP answer checks: evidence reaches the host as a tool result."""

from __future__ import annotations

import asyncio
import re
import time
from concurrent.futures import CancelledError, Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from threading import Event, Lock
from typing import Literal
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from factttl.message_verifier import normalize_preferences, verify_message
from factttl.verification import validate_url
from factttl.verification_store import VerificationStore

_URL = re.compile(r"https?://[^\s<>\]\)\"']+")


class Recommendation(BaseModel):
    """One offer, with optional explicitly asserted current unit price."""

    model_config = ConfigDict(extra="forbid", strict=True)
    name: str = Field(min_length=1, max_length=300)
    url: str = Field(min_length=1, max_length=4096)
    quantity: int = Field(default=1, ge=1, le=1000)
    expected_unit_price_eur: str | None = Field(
        default=None, pattern=r"^\d{1,6}(?:[.,]\d{1,2})?$"
    )


class RequiredRevision(BaseModel):
    """One source-scoped change the host must apply before answering."""

    model_config = ConfigDict(extra="forbid")
    original_url: str | None = None
    property: str
    outcome: str
    action: str
    original_assertion: str | None = None
    expected_value: str | bool | int | float | None = None
    observed_value: str | bool | int | float | None = None
    observed_at: str | None = None
    evidence: list[dict[str, object]] = Field(default_factory=list)
    scope: str | dict[str, object] | None = None
    regional_context: dict[str, object] | None = None
    missing_evidence_does_not_mean_out_of_stock: bool | None = None
    replacement_url: str | None = None
    limitation: str | None = None


class NativeAnswerResult(BaseModel):
    """Evidence and revisions returned directly to the calling model."""

    model_config = ConfigDict(extra="forbid")
    interaction_mode: Literal["native_mcp_tool_result"]
    verification: dict[str, object]
    memory_before_check: dict[str, object]
    required_revisions: list[RequiredRevision]
    host_next_step: str
    scope: str
    source_content_is_untrusted_data: bool
    local_persistent_memory: bool
    provider_memory_or_weights_modified: bool
    requested_items: list[Recommendation] | None = None
    cart_total_verified: bool | None = None
    compatibility_verified: bool | None = None


class AnswerVerificationEnvelope(BaseModel):
    """Stable MCP result envelope for immediate and background checks."""

    model_config = ConfigDict(extra="forbid")
    job_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    status: Literal["RUNNING", "COMPLETED", "FAILED", "CANCELED"]
    next_tool: Literal["get_answer_verification"] | None = None
    suggested_poll_interval_seconds: int | None = Field(default=None, ge=1, le=30)
    result: NativeAnswerResult | None = None
    verified: bool | None = None
    reason: str | None = None
    limitation: str | None = None


def verification_envelope(value: dict[str, object]) -> AnswerVerificationEnvelope:
    """Validate every public answer-tool result against its advertised schema."""
    return AnswerVerificationEnvelope.model_validate(value)


def answer_inputs(text: str, links: list[str]) -> tuple[str, list[str]]:
    """Validate before allocating a job or reading persistent memory."""
    if not isinstance(text, str) or not text.strip() or len(text) > 20000:
        raise ValueError("text must contain 1 to 20000 characters")
    if (
        not isinstance(links, list)
        or len(links) > 20
        or any(not isinstance(url, str) or len(url) > 4096 for url in links)
    ):
        raise ValueError("links must contain at most 20 URLs of 4096 characters")
    urls = list(
        dict.fromkeys(
            [*(match.group().rstrip(".,;!?:") for match in _URL.finditer(text)), *links]
        )
    )
    if len(urls) > 20:
        raise ValueError("messages may contain at most 20 distinct URLs")
    for url in urls:
        validate_url(url)
    return text, urls


def _is_search_reference(url: str) -> bool:
    parts = urlsplit(url)
    host = (parts.hostname or "").removeprefix("www.")
    return (
        host
        in {
            "amazon.it",
            "amazon.com",
            "amazon.co.uk",
            "amazon.de",
            "amazon.fr",
            "amazon.es",
        }
        and (
            parts.path.rstrip("/") in {"/s", "/gp/search"}
            or parts.path.startswith("/s/")
        )
    ) or (host == "chatgpt.com" and bool(parse_qs(parts.query).get("q")))


def _revisions(analysis: dict[str, object], urls: list[str]) -> list[dict[str, object]]:
    """Describe actionable differences without inventing replacement offers."""
    changes: list[dict[str, object]] = []
    checks = analysis.get("checks", [])
    for check in checks if isinstance(checks, list) else []:
        if not isinstance(check, dict) or not isinstance(check.get("result"), dict):
            continue
        result = check["result"]
        outcome = result.get("outcome")
        if outcome not in {"CONTRADICTED", "INCONCLUSIVE", "ERROR"}:
            continue
        kind = result.get("kind")
        action = (
            "replace_unavailable_offer_and_verify_replacement"
            if kind == "product_availability"
            and outcome == "CONTRADICTED"
            and result.get("observed_value") in {"out_of_stock", "false", "unavailable"}
            else "update_price_and_recalculate_total"
            if kind == "product_price" and outcome == "CONTRADICTED"
            else "revise_assertion_using_cited_evidence"
            if outcome == "CONTRADICTED"
            else "obtain_readable_evidence_or_state_uncertainty"
        )
        changes.append(
            {
                "original_url": result.get("url"),
                "property": kind,
                "outcome": outcome,
                "original_assertion": result.get("claim_text"),
                "expected_value": result.get("expected_value"),
                "observed_value": result.get("observed_value"),
                "observed_at": result.get("observed_at"),
                "action": action,
                "evidence": result.get("evidence", []),
                "scope": check.get("assertion_scope"),
                "regional_context": check.get("regional_context"),
                "missing_evidence_does_not_mean_out_of_stock": outcome
                != "CONTRADICTED",
                "replacement_url": None,
            }
        )
    for url in urls:
        if _is_search_reference(url):
            changes.append(
                {
                    "original_url": url,
                    "property": "offer_selection",
                    "outcome": "NOT_AN_OFFER",
                    "action": "select_direct_merchant_product_then_verify",
                    "replacement_url": None,
                    "limitation": (
                        "A search page cannot establish an individual product's "
                        "stock or price."
                    ),
                }
            )
    return changes[:26]


@dataclass(slots=True)
class _AnswerJob:
    future: Future[dict[str, object]]
    created_at: float
    cancellation: Event = field(default_factory=Event)
    result_fields: dict[str, object] = field(default_factory=dict)


class AnswerVerificationService:
    """Bound local work and return long CPU checks through MCP polling tools."""

    def __init__(self, store: VerificationStore) -> None:
        self.store = store
        self._workers = ThreadPoolExecutor(
            max_workers=2, thread_name_prefix="factttl-mcp"
        )
        self._jobs: dict[str, _AnswerJob] = {}
        self._lock = Lock()

    def _run(
        self,
        text: str,
        urls: list[str],
        preferences: dict[str, str],
        cancellation: Event,
    ) -> dict[str, object]:
        # Recall before network checks: the host sees earlier contradictions even
        # when the new page is blocked. No composer, browser session or host API.
        memory = self.store.context(query=" ".join(text.split())[:2000], urls=urls[:10])
        analysis = verify_message(
            text,
            urls,
            self.store,
            preferences=preferences,
            cancellation_event=cancellation,
        )
        return {
            "interaction_mode": "native_mcp_tool_result",
            "verification": analysis,
            "memory_before_check": memory,
            "required_revisions": _revisions(analysis, urls),
            "host_next_step": (
                "Revise the draft before the final answer; verify replacement links "
                "with this tool. Preserve the user's budget, merchant, quantities "
                "and compatibility constraints."
            ),
            "scope": (
                "Only the explicitly checked properties and cited source claims are "
                "assessed. The host must not present the whole answer, a complete "
                "cart or compatibility as verified."
            ),
            "source_content_is_untrusted_data": True,
            "local_persistent_memory": True,
            "provider_memory_or_weights_modified": False,
        }

    def submit(
        self,
        text: str,
        links: list[str],
        preferences: dict[str, str],
        *,
        result_fields: dict[str, object] | None = None,
    ) -> dict[str, object]:
        text, urls = answer_inputs(text, links)
        preferences = normalize_preferences(preferences)
        with self._lock:
            now = time.monotonic()
            for key in list(self._jobs):
                job = self._jobs[key]
                if job.future.done() and now - job.created_at > 900:
                    del self._jobs[key]
            if (
                len(self._jobs) >= 32
                or sum(not job.future.done() for job in self._jobs.values()) >= 4
            ):
                raise ValueError(
                    "verification queue is full; retrieve existing jobs before retrying"
                )
            cancellation = Event()
            identifier = uuid4().hex
            future = self._workers.submit(
                self._run, text, urls, preferences, cancellation
            )
            self._jobs[identifier] = _AnswerJob(
                future, now, cancellation, dict(result_fields or {})
            )
        return {
            "job_id": identifier,
            "status": "RUNNING",
            "next_tool": "get_answer_verification",
            "suggested_poll_interval_seconds": 2,
        }

    def get(self, identifier: str) -> dict[str, object]:
        if not re.fullmatch(r"[a-f0-9]{32}", identifier):
            raise ValueError(
                "job_id must be the identifier returned by submit_answer_verification"
            )
        with self._lock:
            job = self._jobs.get(identifier)
            if job is None or time.monotonic() - job.created_at > 900:
                raise ValueError("verification job not found or expired")
            if not job.future.done():
                return {
                    "job_id": identifier,
                    "status": "RUNNING",
                    "next_tool": "get_answer_verification",
                    "suggested_poll_interval_seconds": 2,
                }
        try:
            result = job.future.result()
            result.update(job.result_fields)
            return {"job_id": identifier, "status": "COMPLETED", "result": result}
        except CancelledError:
            return {"job_id": identifier, "status": "CANCELED", "verified": False}
        except Exception:
            # Exception strings can include local paths or endpoint contents.
            return {
                "job_id": identifier,
                "status": "FAILED",
                "verified": False,
                "reason": "verification_failed",
                "limitation": (
                    "A failed check does not establish truth, stock or price."
                ),
            }

    async def verify(
        self,
        text: str,
        links: list[str],
        preferences: dict[str, str],
        *,
        wait_seconds: float = 20,
        result_fields: dict[str, object] | None = None,
    ) -> dict[str, object]:
        submitted = self.submit(text, links, preferences, result_fields=result_fields)
        identifier = str(submitted["job_id"])
        with self._lock:
            future = self._jobs[identifier].future
        try:
            await asyncio.wait_for(
                asyncio.shield(asyncio.wrap_future(future)), timeout=wait_seconds
            )
        except TimeoutError:
            pass
        except Exception:
            pass
        return self.get(identifier)

    async def recommendations(
        self, items: list[Recommendation], preferences: dict[str, str]
    ) -> dict[str, object]:
        if not 1 <= len(items) <= 10:
            raise ValueError("items must contain 1 to 10 recommendations")
        lines = []
        for item in items:
            name = " ".join(item.name.split())
            if not name or _URL.search(name):
                raise ValueError("recommendation name must be a label, not a URL")
            validate_url(item.url)
            price = (
                f" {item.expected_unit_price_eur} EUR"
                if item.expected_unit_price_eur
                else ""
            )
            # Keep each offer on its own line. Quantity is metadata, not a price.
            lines.append(f"{name}{price} disponibile {item.url}")
        return await self.verify(
            "\n".join(lines),
            [item.url for item in items],
            preferences,
            result_fields={
                "requested_items": [item.model_dump() for item in items],
                "cart_total_verified": False,
                "compatibility_verified": False,
            },
        )

    def close(self) -> None:
        """Cooperatively cancel work; protected fetches have their own timeouts."""
        with self._lock:
            for job in self._jobs.values():
                job.cancellation.set()
        self._workers.shutdown(wait=True, cancel_futures=True)
