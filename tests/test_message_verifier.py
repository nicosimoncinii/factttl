"""Automatic badges remain scoped and preserve uncovered assertions."""

from concurrent.futures import CancelledError
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Event
from typing import Any

import pytest

import factttl.message_verifier as message
import factttl.semantic_provider as semantic
from factttl.verification import VerificationResult
from factttl.verification_store import VerificationStore

URL = "https://example.com/product"


@pytest.fixture
def checks(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, str, str | None]]:
    calls: list[tuple[str, str, str | None]] = []

    def verify(
        url: str, kind: str, expected: str | None, context: str | None, **kwargs: Any
    ) -> VerificationResult:
        calls.append((url, kind, expected))
        return VerificationResult(
            url=url,
            kind=kind,
            outcome="SUPPORTED",
            expected_value=expected,
            claim_text=context,
            observed_at=datetime.now(UTC).isoformat(),
            rationale="Selected property is supported by this test source.",
            evidence=[{"provider": "live_public_web", "field": kind}],
        )

    monkeypatch.setattr(message, "verify_url", verify)
    return calls


def run(tmp_path: Path, text: str, links: list[str] | None = None) -> dict[str, Any]:
    return message.verify_message(
        text, links or [], VerificationStore(tmp_path / "memory.sqlite3")
    )


def test_plain_prose_is_not_marked_true(tmp_path: Path, checks: object) -> None:
    result = run(tmp_path, "Questo dispositivo ha prestazioni eccellenti.")
    assert result["status"] == "INCONCLUSIVE"
    assert result["unchecked_claims"]


def test_http200_does_not_verify_message(tmp_path: Path, checks: object) -> None:
    result = run(tmp_path, f"Questo ESP32 è perfetto per ogni progetto. {URL}")
    assert result["status"] == "PARTIAL"
    assert result["checks"][0]["assertion_scope"]["property"] == "link_available"
    assert result["unchecked_claims"]


def test_explicit_narrow_price_is_checked(
    tmp_path: Path, checks: list[tuple[str, str, str | None]]
) -> None:
    result = run(tmp_path, f"Prezzo: 10,99 EUR {URL}")
    assert (URL, "product_price", "10.99 EUR") in checks
    assert result["status"] == "SUPPORTED"


def test_link_inventory_does_not_associate_prose(
    tmp_path: Path, checks: list[tuple[str, str, str | None]]
) -> None:
    result = run(tmp_path, "Prezzo: 10 EUR", [URL])
    assert checks == [(URL, "link_available", None)]
    assert result["status"] == "PARTIAL"


def test_mixed_products_are_not_associated(
    tmp_path: Path, checks: list[tuple[str, str, str | None]]
) -> None:
    result = run(tmp_path, f"ESP32 10 EUR {URL}; Pico 20 EUR https://example.com/other")
    assert all(kind == "link_available" for _, kind, _ in checks)
    assert result["status"] == "PARTIAL"


def test_negative_stock_is_not_inverted(
    tmp_path: Path, checks: list[tuple[str, str, str | None]]
) -> None:
    run(tmp_path, f"Non è disponibile {URL}")
    assert (URL, "product_availability", "false") in checks
    assert (URL, "product_availability", "true") not in checks


def test_negated_discount_remains_unchecked(tmp_path: Path, checks: object) -> None:
    result = run(tmp_path, f"Prezzo 10 EUR, non in sconto {URL}")
    assert result["status"] == "PARTIAL"
    assert result["unchecked_claims"]


def test_conditional_stock_remains_unchecked(
    tmp_path: Path, checks: list[tuple[str, str, str | None]]
) -> None:
    result = run(tmp_path, f"Se disponibile, acquistalo {URL}")
    assert all(kind == "link_available" for _, kind, _ in checks)
    assert result["status"] == "PARTIAL"


def test_prior_user_correction_prevents_green_badge(
    tmp_path: Path, checks: object
) -> None:
    store = VerificationStore(tmp_path / "memory.sqlite3")
    store.record(
        VerificationResult(
            url=URL,
            kind="claim",
            outcome="CONTRADICTED",
            observed_at=datetime.now(UTC).isoformat(),
            claim_text="Old claim",
            rationale="User correction",
            evidence=[{"provider": "user_report", "correction": "Wrong"}],
        ),
        ttl_seconds=0,
    )
    result = message.verify_message(URL, [], store)
    assert result["status"] == "PARTIAL"
    assert result["prior_corrections"]


def test_contradiction_is_visible(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def verify(
        url: str, kind: str, expected: str | None, context: str | None
    ) -> VerificationResult:
        return VerificationResult(
            url=url,
            kind=kind,
            outcome="CONTRADICTED",
            observed_at=datetime.now(UTC).isoformat(),
            rationale="Missing link",
            evidence=[{"provider": "live_public_web", "status_code": 404}],
        )

    monkeypatch.setattr(message, "verify_url", verify)
    assert run(tmp_path, URL)["status"] == "CONTRADICTED"


def test_bounded_checks(
    tmp_path: Path, checks: list[tuple[str, str, str | None]]
) -> None:
    result = run(tmp_path, "\n".join(f"https://example.com/{i}" for i in range(20)))
    assert len(checks) == 6
    assert result["status"] == "PARTIAL"
    assert result["unchecked_claims"]


def test_empty_message_has_no_claims(tmp_path: Path, checks: object) -> None:
    assert run(tmp_path, " ")["status"] == "NO_CLAIMS"


@pytest.mark.parametrize(
    "prose",
    ["Costa 1 EUR?", "Costava 1 EUR", "Prezzo nel 2020: 1 EUR", "> Costa 1 EUR"],
)
def test_questions_and_old_prices_are_not_current_assertions(
    tmp_path: Path, checks: list[tuple[str, str, str | None]], prose: str
) -> None:
    result = run(tmp_path, prose + " " + URL)
    assert all(kind == "link_available" for _, kind, _ in checks)
    assert result["status"] == "PARTIAL"


def test_cancellation_before_fetch_and_after_fetch_skips_storage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = VerificationStore(tmp_path / "memory.sqlite3")
    cancel = Event()
    cancel.set()
    with pytest.raises(CancelledError):
        message.verify_message(URL, [], store, cancellation_event=cancel)
    cancel.clear()

    def verify(
        url: str, kind: str, expected: str | None, context: str | None
    ) -> VerificationResult:
        cancel.set()
        return VerificationResult(
            url=url,
            kind=kind,
            outcome="SUPPORTED",
            observed_at=datetime.now(UTC).isoformat(),
            rationale="Live source",
            evidence=[{"provider": "live_public_web"}],
        )

    monkeypatch.setattr(message, "verify_url", verify)
    with pytest.raises(CancelledError):
        message.verify_message(URL, [], store, cancellation_event=cancel)
    assert store.recall()["total"] == 0


def test_scan_does_not_persist_entire_chat_text(tmp_path: Path, checks: object) -> None:
    store = VerificationStore(tmp_path / "memory.sqlite3")
    message.verify_message(
        "Private unrelated sentence. Prezzo 10 EUR " + URL, [], store
    )
    for claim in store.recall()["claims"]:
        context = claim["result"]["claim_text"] or ""
        assert "Private unrelated" not in context


def test_news_fetch_and_age_never_establish_truth(
    tmp_path: Path, checks: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    now = datetime.now(UTC)
    monkeypatch.delenv("FACTTTL_NEWS_MODEL", raising=False)
    seen: dict[str, Any] = {}

    def source(url: str, **kwargs: Any) -> dict[str, object]:
        seen.update(kwargs)
        return {
            "observed_at": now.isoformat(),
            "published_at": (now - timedelta(days=20)).isoformat(),
            "title": "A source headline",
            "source_text": "Current source excerpt",
            "status": "FETCHED",
            "final_url": url,
        }

    monkeypatch.setattr(message, "read_source_evidence", source)
    result: dict[str, Any] = message.verify_message(
        "Notizia: annuncia un evento " + URL,
        [],
        VerificationStore(tmp_path / "db"),
        preferences={"country": "DE", "language": "de"},
    )
    news = next(
        check for check in result["checks"] if check["result"]["kind"] == "news"
    )
    assert news["result"]["outcome"] == "INCONCLUSIVE"
    assert news["flags"]["usable_as_current_fact"] is False
    assert news["result"]["evidence"][0]["publication_age_seconds"] == 20 * 86400
    assert news["result"]["evidence"][0]["title"] == "A source headline"
    assert "Notizia non verificata" in news["result"]["rationale"]
    assert result["status"] != "SUPPORTED"
    assert seen["language"] == "de"


def test_implicit_amazon_stock_and_price_observation(
    tmp_path: Path, checks: list[tuple[str, str, str | None]]
) -> None:
    url = "https://www.amazon.it/dp/B012345678"
    result = run(tmp_path, url)
    assert (url, "product_availability", "true") in checks
    assert (url, "product_price", None) in checks
    price = next(
        check
        for check in result["checks"]
        if check["result"]["kind"] == "product_price"
    )
    assert price["observation_only"] is True
    stock = next(
        check
        for check in result["checks"]
        if check["result"]["kind"] == "product_availability"
    )
    assert stock["implicit_recommendation_check"] is True


def test_explicit_negative_stock_overrides_implicit_recommendation(
    tmp_path: Path, checks: list[tuple[str, str, str | None]]
) -> None:
    url = "https://amazon.it/dp/B012345678"
    run(tmp_path, "Non disponibile " + url)
    assert (url, "product_availability", "false") in checks
    assert (url, "product_availability", "true") not in checks


def test_marketplace_mismatch_is_not_personalized_support(
    tmp_path: Path, checks: object
) -> None:
    result: dict[str, Any] = message.verify_message(
        "https://amazon.it/dp/B012345678",
        [],
        VerificationStore(tmp_path / "db"),
        preferences={"country": "US", "language": "en"},
    )
    assert result["status"] != "SUPPORTED"
    assert all(check["regional_context"]["warning"] for check in result["checks"])


@pytest.mark.parametrize(
    "preferences",
    [
        {"country": "RU", "language": "it"},
        {"country": "IT", "language": "it\r\nHeader:x"},
        {"country": "IT"},
        "IT",
        {"country": True, "language": "it"},
    ],
)
def test_invalid_preferences_rejected(preferences: object) -> None:
    with pytest.raises(ValueError):
        message.normalize_preferences(preferences)


@pytest.mark.parametrize("outcome", ["SUPPORTED", "CONTRADICTED"])
def test_semantic_news_uses_full_live_body_and_persists_scoped_claim(
    tmp_path: Path, checks: object, monkeypatch: pytest.MonkeyPatch, outcome: str
) -> None:
    now = datetime.now(UTC).isoformat()
    quote = "The launch was canceled and the original event will not take place."
    body = "Introductory background. " * 10 + quote
    captured: dict[str, Any] = {}

    def source(url: str, **kwargs: Any) -> dict[str, object]:
        return {
            "observed_at": now,
            "published_at": None,
            "title": "A headline",
            "source_text": body,
            "status": "FETCHED",
            "final_url": url,
        }

    def assess(
        claim_text: str, source_text: str, source_url: str, **kwargs: Any
    ) -> dict[str, object]:
        captured.update(
            claim=claim_text, body=source_text, source_url=source_url, **kwargs
        )
        return {
            "outcome": outcome,
            "rationale": "Consistency with the source body only.",
            "citations": [
                {"quote": quote, "source_url": source_url, "source_id": "source-1"}
            ],
            "engine": "ollama_local",
            "configured": True,
            "model": "local-test",
            "scope": "current_source_consistency",
            "provider": "ai_assessed_live_source",
        }

    monkeypatch.setattr(message, "read_source_evidence", source)
    monkeypatch.setattr(semantic, "assess_news_claim", assess)
    store = VerificationStore(tmp_path / "db")
    result: dict[str, Any] = message.verify_message(
        "Private unrelated information. Notizia: l'evento è stato annullato " + URL,
        [],
        store,
        preferences={"country": "IT", "language": "it"},
    )
    news = next(item for item in result["checks"] if item["result"]["kind"] == "news")
    assert news["result"]["outcome"] == outcome
    assert captured["body"] == body
    assert "Private unrelated" not in captured["claim"]
    assert captured["source_observed_at"] == now
    assert news["result"]["evidence"][1]["semantic_assessment"] == outcome
    stored = next(
        item for item in store.recall()["claims"] if item["result"]["kind"] == "news"
    )
    assert stored["assertion_scope"]["assessment_scope"] == "current_source_consistency"
    assert stored["assertion_scope"]["claim_text_is_context_only"] is False
    assert stored["independently_verified"] is False


def test_semantic_news_with_fabricated_quote_stays_inconclusive(
    tmp_path: Path, checks: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        message,
        "read_source_evidence",
        lambda url, **kwargs: {
            "observed_at": datetime.now(UTC).isoformat(),
            "published_at": None,
            "title": "Event occurs tomorrow",
            "source_text": "The source gives no such assurance.",
            "status": "FETCHED",
            "final_url": url,
        },
    )
    monkeypatch.setattr(
        semantic,
        "assess_news_claim",
        lambda *args, **kwargs: {
            "outcome": "SUPPORTED",
            "rationale": "A fabricated assessment",
            "citations": [{"quote": "Event occurs tomorrow", "source_url": URL}],
            "engine": "ollama_local",
            "configured": True,
            "model": "local-test",
        },
    )
    result = run(tmp_path, "Notizia: l'evento avviene domani " + URL)
    news = next(item for item in result["checks"] if item["result"]["kind"] == "news")
    assert news["result"]["outcome"] == "INCONCLUSIVE"
    assert news["flags"]["usable_as_current_fact"] is False


def test_news_question_has_no_assertion_for_local_model(
    tmp_path: Path, checks: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        message,
        "read_source_evidence",
        lambda url, **kwargs: {
            "observed_at": datetime.now(UTC).isoformat(),
            "published_at": None,
            "title": "Source",
            "source_text": "Current body",
            "status": "FETCHED",
            "final_url": url,
        },
    )
    monkeypatch.setattr(
        semantic,
        "assess_news_claim",
        lambda *args, **kwargs: pytest.fail("A question is not an assertion"),
    )
    result = run(tmp_path, "Questa notizia è vera? " + URL)
    news = next(item for item in result["checks"] if item["result"]["kind"] == "news")
    assert news["result"]["outcome"] == "INCONCLUSIVE"


@pytest.mark.parametrize(
    "verdicts,expected",
    [
        (["SUPPORTED", "SUPPORTED"], "SUPPORTED"),
        (["SUPPORTED", "CONTRADICTED"], "INCONCLUSIVE"),
        (["SUPPORTED", "INCONCLUSIVE"], "INCONCLUSIVE"),
    ],
)
def test_provided_news_sources_must_agree_before_persisting(
    tmp_path: Path,
    checks: object,
    monkeypatch: pytest.MonkeyPatch,
    verdicts: list[str],
    expected: str,
) -> None:
    urls = ["https://one.example/article", "https://two.example/article"]

    def observe(
        url: str, language: object, claim: str, country: str, cancellation: object
    ) -> VerificationResult:
        return VerificationResult(
            url=url,
            kind="news",
            outcome=verdicts[urls.index(url)],
            claim_text=claim,
            observed_at=datetime.now(UTC).isoformat(),
            rationale="Scoped test assessment",
            evidence=[
                {
                    "provider": "ai_assessed_live_source",
                    "scope": "current_source_consistency",
                    "url": url,
                }
            ],
        )

    monkeypatch.setattr(message, "_news_observation", observe)
    result = run(
        tmp_path, "Notizia: il lancio ufficiale avviene domani " + " ".join(urls)
    )
    news = [check for check in result["checks"] if check["result"]["kind"] == "news"]
    assert len(news) == 2
    assert all(check["result"]["outcome"] == expected for check in news)
    assert all(check["result"]["evidence"][-2]["source_count"] == 2 for check in news)
    assert all(
        check["result"]["evidence"][-2]["independence_established"] is False
        for check in news
    )


def test_configured_engine_checks_linked_statement_without_news_keyword(
    tmp_path: Path,
    checks: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FACTTTL_NEWS_MODEL", "local-test")
    seen = []

    def observe(
        url: str, language: object, claim: str, country: str, cancellation: object
    ) -> VerificationResult:
        seen.append(claim)
        return VerificationResult(
            url=url,
            kind="news",
            outcome="INCONCLUSIVE",
            claim_text=claim,
            observed_at=datetime.now(UTC).isoformat(),
            rationale="Insufficient evidence",
            evidence=[],
        )

    monkeypatch.setattr(message, "_news_observation", observe)
    run(tmp_path, "Il lancio ufficiale avviene il dodici ottobre " + URL)
    assert seen == ["Il lancio ufficiale avviene il dodici ottobre"]


def test_long_article_is_explicitly_an_excerpt_not_full_article_confirmation(
    tmp_path: Path,
    checks: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    quote = "Il lancio ufficiale avverrà il 12 ottobre 2026."
    body = quote + " Background estraneo." * 700
    seen: list[str] = []
    monkeypatch.setattr(
        message,
        "read_source_evidence",
        lambda url, **kwargs: {
            "observed_at": datetime.now(UTC).isoformat(),
            "published_at": None,
            "source_text": body,
            "status": "FETCHED",
            "final_url": url,
        },
    )

    def assess(claim: str, text: str, url: str, **kwargs: Any) -> dict[str, object]:
        seen.append(text)
        return {
            "outcome": "SUPPORTED",
            "rationale": "L'estratto concorda.",
            "citations": [{"quote": quote, "source_url": url}],
            "engine": "ollama_local",
            "configured": True,
        }

    monkeypatch.setattr(semantic, "assess_news_claim", assess)
    result = run(
        tmp_path, "Notizia: il lancio ufficiale avverrà il 12 ottobre 2026 " + URL
    )
    news = next(
        check for check in result["checks"] if check["result"]["kind"] == "news"
    )
    assert seen == [body[:1500]]
    assert news["result"]["evidence"][1]["analysis_scope"] == "excerpt_consistency"
    assert news["result"]["evidence"][1]["source_analysis_truncated"] is True


@pytest.mark.parametrize("text,links", [("x" * 20001, []), ("x", [URL] * 21)])
def test_size_bounds(tmp_path: Path, text: str, links: list[str]) -> None:
    with pytest.raises(ValueError):
        run(tmp_path, text, links)
