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


@pytest.mark.parametrize(
    "price",
    [
        "Prezzo indicativo 8 EUR",
        "Prezzo ~8 EUR",
        "Prezzo 5–8 EUR",
        "Prezzo circa 8 EUR",
    ],
)
def test_product_estimates_observe_current_price_without_exact_assertion(
    tmp_path: Path,
    checks: list[tuple[str, str, str | None]],
    price: str,
) -> None:
    url = "https://www.amazon.it/gp/aw/d/B0DKF9NCN1"
    run(tmp_path, f"ESP32 {price} {url}")
    assert (url, "product_price", None) in checks
    assert not any(
        kind == "product_price" and expected is not None for _, kind, expected in checks
    )


def test_amazon_search_is_not_an_offer(
    tmp_path: Path,
    checks: list[tuple[str, str, str | None]],
) -> None:
    url = "https://www.amazon.it/s?k=esp32"
    result = run(tmp_path, f"ESP32 disponibile a 8 EUR {url}")
    assert checks == [(url, "link_available", None)]
    assert result["unchecked_claims"]


def test_wrapped_amazon_recommendation_observes_stock_and_price(
    tmp_path: Path,
    checks: list[tuple[str, str, str | None]],
) -> None:
    url = "https://www.amazon.it/sspa/click?url=%2Fdp%2FB0DKF9NCN1"
    run(tmp_path, f"ESP32 raccomandato {url}")
    assert (url, "product_availability", "true") in checks
    assert (url, "product_price", None) in checks


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
    assert captured["source_published_at"] is None
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


def test_news_reader_passes_old_publication_separately_from_fresh_observation(
    tmp_path: Path,
    checks: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = datetime.now(UTC).isoformat()
    published = "2024-01-01T00:00:00+00:00"
    captured: dict[str, Any] = {}
    monkeypatch.setattr(
        message,
        "read_source_evidence",
        lambda url, **k: {
            "status": "FETCHED",
            "final_url": url,
            "observed_at": now,
            "published_at": published,
            "source_text": "Nel 2024 Mario era presidente della commissione.",
        },
    )

    def assess(claim: str, text: str, url: str, **kwargs: Any) -> dict[str, object]:
        captured.update(kwargs)
        return {
            "outcome": "INCONCLUSIVE",
            "rationale": "L'archivio non stabilisce il ruolo attuale.",
            "engine": "ollama_local",
            "configured": True,
            "citations": [],
        }

    monkeypatch.setattr(semantic, "assess_news_claim", assess)
    result = run(tmp_path, "Notizia: Mario è oggi presidente della commissione " + URL)
    assert captured["source_published_at"] == published
    assert captured["source_observed_at"] == now
    news = next(
        check["result"]
        for check in result["checks"]
        if check["result"]["kind"] == "news"
    )
    assert news["outcome"] == "INCONCLUSIVE"
    assert news["published_at"] == published


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
        (["SUPPORTED", "INCONCLUSIVE"], "MIXED"),
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
    assert [check["result"]["outcome"] for check in news] == (
        verdicts if expected == "MIXED" else [expected, expected]
    )
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


@pytest.mark.parametrize("provided", [False, True])
def test_opt_in_discovery_reads_real_candidate_pages_once(
    tmp_path: Path,
    checks: object,
    monkeypatch: pytest.MonkeyPatch,
    provided: bool,
) -> None:
    from factttl import source_discovery

    monkeypatch.setenv("FACTTTL_NEWS_DISCOVERY", "bing")
    candidate_urls = [
        "https://one.example/article",
        "https://www.one.example/duplicate",
        "https://two.example/article",
    ]
    discovery_calls = []

    def discover(claim: str, **kwargs: Any) -> dict[str, object]:
        discovery_calls.append(claim)
        return {
            "status": "FOUND",
            "urls": candidate_urls,
            "candidate_count": 3,
            "query_sent": True,
        }

    seen = []

    def observe(
        url: str, language: object, claim: str, country: str, cancellation: object
    ) -> VerificationResult:
        seen.append(url)
        return VerificationResult(
            url=url,
            kind="news",
            outcome="SUPPORTED",
            claim_text=claim,
            observed_at=datetime.now(UTC).isoformat(),
            rationale="Scoped agreement",
            evidence=[
                {
                    "provider": "ai_assessed_live_source",
                    "scope": "current_source_consistency",
                }
            ],
        )

    monkeypatch.setattr(source_discovery, "discover_sources", discover)
    monkeypatch.setattr(message, "_news_observation", observe)
    text = "Notizia: NASA annuncia il lancio Artemis domani" + (
        " " + URL if provided else ""
    )
    result = run(tmp_path, text)
    assert len(discovery_calls) == 1
    assert set(seen) == {
        candidate_urls[0],
        candidate_urls[2],
        *([URL] if provided else []),
    }
    assert len(seen) == len(set(seen))
    assert result["discovery"]["queries_sent"] == 1
    news = [check for check in result["checks"] if check["result"]["kind"] == "news"]
    assert all(check["result"]["outcome"] == "SUPPORTED" for check in news)
    assert all(
        any(
            e["provider"] == "public_source_discovery"
            for e in check["result"]["evidence"]
        )
        for check in news
    )
    assert all(
        e["fetched_source_count"] == 0
        for check in news
        for e in check["result"]["evidence"]
        if e["provider"] == "public_source_discovery"
    )  # Selecting a candidate is not proof that its body was fetched.


def test_empty_discovery_preserves_grounded_original_source_scope(
    tmp_path: Path,
    checks: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from factttl import source_discovery

    monkeypatch.setenv("FACTTTL_NEWS_DISCOVERY", "bing")
    monkeypatch.setattr(
        source_discovery,
        "discover_sources",
        lambda *a, **k: {
            "status": "EMPTY",
            "urls": [],
            "candidate_count": 0,
            "query_sent": True,
        },
    )
    monkeypatch.setattr(
        message,
        "_news_observation",
        lambda url, lang, claim, country, cancel: VerificationResult(
            url=url,
            kind="news",
            outcome="SUPPORTED",
            claim_text=claim,
            observed_at=datetime.now(UTC).isoformat(),
            rationale="One source says so",
            evidence=[
                {
                    "provider": "ai_assessed_live_source",
                    "scope": "current_source_consistency",
                }
            ],
        ),
    )
    result = run(tmp_path, "Notizia: NASA annuncia il lancio Artemis domani " + URL)
    news = next(
        check for check in result["checks"] if check["result"]["kind"] == "news"
    )
    assert news["result"]["outcome"] == "SUPPORTED"
    comparison = next(
        e
        for e in news["result"]["evidence"]
        if e["provider"] == "provided_source_comparison"
    )
    assert comparison["corroboration_complete"] is False
    assert comparison["assessment_basis_urls"] == [URL]


@pytest.mark.parametrize("outcome", ["SUPPORTED", "CONTRADICTED"])
def test_grounded_excerpt_verdict_survives_grouping_with_clear_scope(
    tmp_path: Path,
    checks: object,
    monkeypatch: pytest.MonkeyPatch,
    outcome: str,
) -> None:
    urls = ["https://one.example/article", "https://two.example/article"]

    def observe(
        url: str, language: object, claim: str, country: str, cancellation: object
    ) -> VerificationResult:
        return VerificationResult(
            url=url,
            kind="news",
            outcome=outcome,
            claim_text=claim,
            observed_at=datetime.now(UTC).isoformat(),
            rationale="The quoted excerpt explicitly addresses this claim.",
            evidence=[
                {
                    "provider": "ai_assessed_live_source",
                    "scope": "current_source_consistency",
                    "source_analysis_truncated": True,
                    "analysis_scope": "excerpt_consistency",
                }
            ],
        )

    monkeypatch.setattr(message, "_news_observation", observe)
    result = run(
        tmp_path, "Notizia: il lancio ufficiale avviene domani " + " ".join(urls)
    )
    news = [check for check in result["checks"] if check["result"]["kind"] == "news"]
    assert all(check["result"]["outcome"] == outcome for check in news)
    comparison = news[0]["result"]["evidence"][-2]
    assert comparison["assessment_scope"] == "inspected_evidence_consistency"
    assert comparison["corroboration_complete"] is False
    assert comparison["assessment_basis_urls"] == urls
    assert comparison["independence_established"] is False


def test_browser_offer_used_for_matching_asin_before_http(
    tmp_path: Path,
    checks: list[tuple[str, str, str | None]],
) -> None:
    url = "https://www.amazon.it/dp/B012345678"
    observation = {
        "url": url + "?ref=test",
        "asin": "B012345678",
        "observed_at": datetime.now(UTC).isoformat(),
        "source": "browser_rendered_amazon",
        "scope": "browser_current_offer",
        "status": "OBSERVED",
        "title": "ESP32 test product",
        "availability": "unavailable",
        "price": "10.99",
        "currency": "EUR",
    }
    result: dict[str, Any] = message.verify_message(
        "Prezzo: 1 EUR " + url,
        [],
        VerificationStore(tmp_path / "browser.db"),
        browser_observations=[observation],
        preferences={"country": "US", "language": "en"},
    )
    products = [
        check
        for check in result["checks"]
        if check["result"]["kind"].startswith("product_")
    ]
    assert all(check["result"]["outcome"] == "CONTRADICTED" for check in products)
    assert all(
        check["result"]["evidence"][0]["product_title"] == "ESP32 test product"
        for check in products
    )
    assert all(check["regional_context"]["warning"] for check in products)
    assert checks == [(url, "link_available", None)]


def test_other_product_observation_cannot_override_linked_offer(
    tmp_path: Path,
    checks: list[tuple[str, str, str | None]],
) -> None:
    url = "https://www.amazon.it/dp/B012345678"
    observation = {
        "url": "https://www.amazon.it/dp/B012345679",
        "asin": "B012345679",
        "observed_at": datetime.now(UTC).isoformat(),
        "source": "browser_rendered_amazon",
        "scope": "browser_current_offer",
        "status": "OBSERVED",
        "title": "Other product",
        "availability": "unavailable",
    }
    message.verify_message(
        url,
        [],
        VerificationStore(tmp_path / "browser.db"),
        browser_observations=[observation],
    )
    assert (url, "product_availability", "true") in checks
    assert (url, "product_price", None) in checks


def test_browser_available_offer_and_one_euro_claim_have_separate_verdicts(
    tmp_path: Path,
    checks: list[tuple[str, str, str | None]],
) -> None:
    url = "https://www.amazon.it/dp/B012345678"
    observation = {
        "url": url,
        "asin": "B012345678",
        "observed_at": datetime.now(UTC).isoformat(),
        "source": "browser_rendered_amazon",
        "scope": "browser_current_offer",
        "status": "OBSERVED",
        "title": "ESP32 test product",
        "availability": "available",
        "price": "10.99",
        "currency": "EUR",
    }
    result: dict[str, Any] = message.verify_message(
        "Prezzo: 1,00 EUR, disponibile " + url,
        [],
        VerificationStore(tmp_path / "browser.db"),
        browser_observations=[observation],
    )
    products = {
        check["result"]["kind"]: check["result"]
        for check in result["checks"]
        if check["result"]["kind"].startswith("product_")
    }
    assert products["product_availability"]["outcome"] == "SUPPORTED"
    assert products["product_price"]["outcome"] == "CONTRADICTED"
    assert products["product_price"]["expected_value"] == "1.00 EUR"
    assert products["product_price"]["observed_value"] == "10.99 EUR"
    assert checks == [(url, "link_available", None)]


def test_other_seller_observation_does_not_override_same_asin(
    tmp_path: Path,
    checks: list[tuple[str, str, str | None]],
) -> None:
    url = "https://www.amazon.it/dp/B012345678?smid=SELLER_A"
    observation = {
        "url": "https://www.amazon.it/dp/B012345678?smid=SELLER_B",
        "asin": "B012345678",
        "observed_at": datetime.now(UTC).isoformat(),
        "source": "browser_rendered_amazon",
        "scope": "browser_current_offer",
        "status": "OBSERVED",
        "title": "Other seller offer",
        "availability": "unavailable",
    }
    message.verify_message(
        url,
        [],
        VerificationStore(tmp_path / "browser.db"),
        browser_observations=[observation],
    )
    assert (url, "product_availability", "true") in checks
    assert (url, "product_price", None) in checks


def test_no_discovery_when_disabled(
    tmp_path: Path, checks: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    from factttl import source_discovery

    monkeypatch.delenv("FACTTTL_NEWS_DISCOVERY", raising=False)
    monkeypatch.setattr(
        source_discovery,
        "discover_sources",
        lambda *a, **k: pytest.fail("Discovery must be opt-in"),
    )
    result = run(tmp_path, "Notizia: NASA annuncia il lancio Artemis domani")
    assert result["discovery"]["enabled"] is False


def test_discovered_source_recalls_prior_scoped_correction(
    tmp_path: Path,
    checks: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from factttl import source_discovery

    monkeypatch.setenv("FACTTTL_NEWS_DISCOVERY", "bing")
    url = "https://one.example/article"
    store = VerificationStore(tmp_path / "memory.sqlite3")
    old_claim = "Notizia precedente: il lancio avviene oggi."
    store.record(
        VerificationResult(
            url=url,
            kind="news",
            outcome="CONTRADICTED",
            claim_text=old_claim,
            observed_at=datetime.now(UTC).isoformat(),
            rationale="The source explicitly denies that earlier date.",
            evidence=[
                {
                    "provider": "ai_assessed_live_source",
                    "scope": "current_source_consistency",
                }
            ],
        ),
        ttl_seconds=300,
    )
    monkeypatch.setattr(
        source_discovery,
        "discover_sources",
        lambda *a, **k: {
            "status": "FOUND",
            "urls": [url],
            "candidate_count": 1,
            "query_sent": True,
        },
    )
    monkeypatch.setattr(
        message,
        "_news_observation",
        lambda url, lang, claim, country, cancel: VerificationResult(
            url=url,
            kind="news",
            outcome="INCONCLUSIVE",
            claim_text=claim,
            observed_at=datetime.now(UTC).isoformat(),
            rationale="New statement needs evidence",
            evidence=[],
        ),
    )
    result: dict[str, Any] = message.verify_message(
        "Notizia: NASA annuncia il lancio Artemis domani", [], store
    )
    assert result["prior_corrections"][0]["claim_text"] == old_claim
    assert result["prior_corrections"][0]["url"] == url


def test_discovery_time_budget_reports_no_fetched_evidence(
    tmp_path: Path,
    checks: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import time

    from factttl import source_discovery

    ticks = iter([0.0, 60.0])
    monkeypatch.setattr(time, "monotonic", lambda: next(ticks, 60.0))
    monkeypatch.setenv("FACTTTL_NEWS_DISCOVERY", "bing")
    monkeypatch.setattr(
        source_discovery,
        "discover_sources",
        lambda *a, **k: {
            "status": "FOUND",
            "urls": ["https://one.example/article"],
            "candidate_count": 1,
            "query_sent": True,
        },
    )
    monkeypatch.setattr(
        message,
        "_news_observation",
        lambda *a, **k: pytest.fail(
            "Do not start a fetch/inference without sufficient budget"
        ),
    )
    result = run(tmp_path, "Notizia: NASA annuncia il lancio Artemis domani")
    news = result["checks"][0]["result"]
    assert news["outcome"] == "INCONCLUSIVE"
    assert (
        next(e for e in news["evidence"] if e["provider"] == "public_source_discovery")[
            "fetched_source_count"
        ]
        == 0
    )


@pytest.mark.parametrize(
    "claim",
    [
        "In Toscana dal 2026 l'installazione di sensori è obbligatoria.",
        "Il presidente degli Stati Uniti è Donald Trump.",
        "Mozilla ha rilasciato Firefox 142 il 19 agosto 2025.",
    ],
)
def test_public_claim_without_news_marker_is_discovered_and_grounded(
    tmp_path: Path,
    checks: object,
    monkeypatch: pytest.MonkeyPatch,
    claim: str,
) -> None:
    from factttl import source_discovery

    monkeypatch.setenv("FACTTTL_NEWS_DISCOVERY", "bing")
    seen = []
    url = "https://public.example/article"

    def discover(text: str, **kwargs: Any) -> dict[str, object]:
        seen.append(text)
        return {
            "status": "FOUND",
            "urls": [url],
            "candidate_count": 1,
            "query_sent": True,
        }

    monkeypatch.setattr(source_discovery, "discover_sources", discover)
    monkeypatch.setattr(
        message,
        "read_source_evidence",
        lambda url, **k: {
            "status": "FETCHED",
            "final_url": url,
            "observed_at": datetime.now(UTC).isoformat(),
            "source_text": claim,
            "published_at": None,
        },
    )
    monkeypatch.setattr(
        semantic,
        "assess_news_claim",
        lambda text, body, source_url, **k: {
            "outcome": "SUPPORTED",
            "rationale": "La fonte riporta la stessa affermazione.",
            "engine": "ollama_local",
            "configured": True,
            "citations": [{"quote": claim, "source_url": source_url}],
        },
    )
    result = run(tmp_path, "Informazione personale estranea. " + claim)
    assert seen == [claim]
    news = next(
        check["result"]
        for check in result["checks"]
        if check["result"]["kind"] == "news"
    )
    assert news["outcome"] == "SUPPORTED"
    assert news["claim_text"] == claim
    assert news["evidence"][1]["citations"][0]["quote"] == claim


@pytest.mark.parametrize(
    "text",
    [
        "Il direttore di questa società si chiama Mario Rossi.",
        "Notizia: Mario Rossi ha cambiato appuntamento domani.",
        "Notizia: il mio collega ha annunciato che lavora alla NASA.",
        "Mozilla Firefox è il migliore browser disponibile.",
        "Il presidente degli Stati Uniti potrebbe essere Donald Trump.",
        "Chi è il presidente degli Stati Uniti?",
        "In Toscana dal 2026 potrebbe diventare obbligatorio un sensore.",
        "Io ho annunciato alla NASA i dettagli del mio appuntamento.",
        "Mozilla ha inviato la release a mario@example.com ieri.",
        "Il CEO di Acme si chiama Mario Rossi.",
    ],
)
def test_private_unknown_or_uncertain_unlinked_prose_is_not_searched(
    tmp_path: Path,
    checks: object,
    monkeypatch: pytest.MonkeyPatch,
    text: str,
) -> None:
    from factttl import source_discovery

    monkeypatch.setenv("FACTTTL_NEWS_DISCOVERY", "bing")
    monkeypatch.setattr(
        source_discovery,
        "discover_sources",
        lambda *a, **k: pytest.fail("Do not search private/unknown/opinion text"),
    )
    result = run(tmp_path, text)
    assert result["status"] == "INCONCLUSIVE"
    assert result["discovery"]["queries_sent"] == 0


@pytest.mark.parametrize("text,links", [("x" * 20001, []), ("x", [URL] * 21)])
def test_size_bounds(tmp_path: Path, text: str, links: list[str]) -> None:
    with pytest.raises(ValueError):
        run(tmp_path, text, links)
