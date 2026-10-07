"""Conservative automatic checks of explicitly URL-associated message fragments."""

from __future__ import annotations

import re
from concurrent.futures import CancelledError, ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime
from threading import Event
from urllib.parse import urlsplit

from factttl.verification import VerificationResult, parse_timestamp
from factttl.verification_store import VerificationStore
from factttl.web_verifier import read_source_evidence, verify_url

_URL = re.compile(r"https?://[^\s<>\]\)\"']+")
_PRICE = re.compile(
    r"(?<![\d.,])(?:€\s*(\d{1,6}(?:[.,]\d{1,2})?)"
    r"|(\d{1,6}(?:[.,]\d{1,2})?)\s*(?:€|EUR\b))(?![\d.,])",
    re.I,
)
_NEGATIVE = re.compile(
    r"\b(?:non\s+(?:è\s+)?disponibile|not\s+available|esaurit[oa]|"
    r"out of stock|unavailable)\b",
    re.I,
)
_POSITIVE = re.compile(r"\b(?:disponibile|in stock|available)\b", re.I)
_DISCOUNT = re.compile(r"\b(?:in sconto|scontat[oa]|discounted|on sale)\b", re.I)
_NEWS = re.compile(
    r"\b(?:annuncia|annuncio|notizia|notizie|latest|published|headline|news|"
    r"breaking|pubblicat[oa]|articolo|article|reported)\b",
    re.I,
)
_CONDITIONAL = re.compile(
    r"\b(?:se|forse|potrebbe|if|might|possibly|ipotetic[oa]|costava|"
    r"precedentemente|precedente|vecchi[oa]|passato|ieri|prima|era|was|"
    r"previously|historical|formerly|yesterday|said|diceva)\b",
    re.I,
)
_BOILERPLATE = re.compile(
    r"\b(?:prezzo|price|costa|costs|disponibile|non|esaurito|esaurita|available|"
    r"unavailable|in|stock|out|sconto|scontato|scontata|discounted|on|sale|link|"
    r"url|acquista|qui|buy|here|prodotto|product|è|is|a|at|di|the)\b",
    re.I,
)
_LABELS = {
    "SUPPORTED": "Dati circoscritti confermati",
    "CONTRADICTED": "Contiene dati in contrasto con la fonte",
    "INCONCLUSIVE": "Non verificabile automaticamente",
    "PARTIAL": "Verifica parziale",
    "NO_CLAIMS": "Nessuna verifica applicabile",
}

COUNTRIES = frozenset({"IT", "US", "GB", "DE", "FR", "ES"})
LANGUAGES = frozenset({"it", "en", "de", "fr", "es"})


def normalize_preferences(preferences: object = None) -> dict[str, str]:
    """Validate hints without inferring location or personalized availability."""
    if preferences is None:
        return {"country": "IT", "language": "it"}
    if not isinstance(preferences, dict) or set(preferences) != {"country", "language"}:
        raise ValueError("preferences must contain country and language")
    country, language = preferences["country"], preferences["language"]
    if not isinstance(country, str) or not isinstance(language, str):
        raise ValueError("country and language must be strings")
    country, language = country.strip().upper(), language.strip().lower()
    if country not in COUNTRIES or language not in LANGUAGES:
        raise ValueError("unsupported country or language")
    return {"country": country, "language": language}


def _news_observation(
    url: str,
    language: str | None,
    claim_text: str | None,
    country: str,
    cancellation_event: Event | None = None,
) -> VerificationResult:
    source = (
        read_source_evidence(url, language=language)
        if language is not None
        else read_source_evidence(url)
    )
    observed = str(source["observed_at"])
    published = source.get("published_at")
    published = published if isinstance(published, str) else None
    age: int | None = None
    if published is not None:
        delta = (parse_timestamp(observed) - parse_timestamp(published)).total_seconds()
        age = max(0, int(delta)) if delta >= 0 else None
    evidence: list[dict[str, object]] = [
        {
            "provider": "live_public_web"
            if source["status"] == "FETCHED"
            else "source_fetch_attempt",
            "source": "live_news_source",
            "trust": "untrusted_page_content",
            "url": source["final_url"],
            "title": source.get("title", ""),
            "source_excerpt": str(source.get("source_text", ""))[:500],
            "published_at": published,
            "publication_age_seconds": age,
            "source_status": source["status"],
            "semantic_assessment": "NOT_VERIFIED",
            "language_hint": language,
        }
    ]
    outcome = "ERROR" if source["status"] == "ERROR" else "INCONCLUSIVE"
    rationale = (
        "Notizia non verificata: serve un confronto con fonti pertinenti e "
        "una valutazione del contenuto. Titolo e data della pagina non provano "
        "che l'affermazione sia vera o ancora attuale."
    )
    if source["status"] == "FETCHED" and claim_text:
        if cancellation_event is not None and cancellation_event.is_set():
            raise CancelledError("Message verification canceled")
        from factttl.semantic_provider import assess_news_claim

        assessment = assess_news_claim(
            claim_text,
            str(source.get("source_text", ""))[:12000],
            str(source["final_url"]),
            language=language or "it",
            country=country,
            source_observed_at=observed,
        )
        outcome = str(assessment["outcome"])
        rationale = str(assessment["rationale"])[:7500]
        source_text = " ".join(str(source.get("source_text", "")).split())
        citations = assessment.get("citations")
        if outcome in {"SUPPORTED", "CONTRADICTED"} and (
            not isinstance(citations, list)
            or not citations
            or any(
                not isinstance(citation, dict)
                or citation.get("source_url") != source["final_url"]
                or not isinstance(citation.get("quote"), str)
                or not 20 <= len(citation["quote"]) <= 1000
                or " ".join(citation["quote"].split()) not in source_text
                for citation in citations
            )
        ):
            outcome = "INCONCLUSIVE"
            rationale = (
                "Notizia non verificata: le citazioni non sono ancorate "
                "al contenuto della fonte letta."
            )
            citations = []
        evidence[0]["semantic_assessment"] = outcome
        evidence.append(
            {
                "provider": "ai_assessed_live_source",
                "source": "local_news_assessment",
                "scope": "current_source_consistency",
                "engine": assessment["engine"],
                "configured": assessment["configured"],
                "model": assessment.get("model"),
                "assessment": outcome,
                "semantic_assessment": outcome,
                "citations": citations if isinstance(citations, list) else [],
                "limitation": (
                    "Semantic consistency with this fetched source; "
                    "not universal truth or independent corroboration."
                ),
            }
        )
    return VerificationResult(
        url=url,
        kind="news",
        outcome=outcome,
        observed_at=observed,
        published_at=published,
        rationale=rationale,
        evidence=evidence,
        claim_text=claim_text,
        observed_value=f"publication_age_seconds={age}" if age is not None else None,
    )


def verify_message(
    text: str,
    links: list[str],
    store: VerificationStore,
    *,
    cancellation_event: Event | None = None,
    preferences: dict[str, str] | None = None,
) -> dict[str, object]:
    """Check links and narrowly linked stock/price statements, never entire truth.

    The browser must place anchor URLs inline in their original text location.
    External link inventory alone cannot associate a price with a product.
    """

    def check_cancellation() -> None:
        if cancellation_event is not None and cancellation_event.is_set():
            raise CancelledError("Message verification canceled")

    check_cancellation()
    region = normalize_preferences(preferences)
    language = region["language"] if preferences is not None else None
    if not isinstance(text, str) or len(text) > 20000:
        raise ValueError("text must contain at most 20000 characters")
    if (
        not isinstance(links, list)
        or len(links) > 20
        or any(not isinstance(url, str) or len(url) > 4096 for url in links)
    ):
        raise ValueError(
            "links must contain at most 20 URL strings of at most 4096 characters"
        )
    found = [_clean_url(match.group()) for match in _URL.finditer(text)]
    urls = list(dict.fromkeys([*found, *links]))
    if len(urls) > 20:
        raise ValueError("messages may contain at most 20 distinct URLs")
    checks: list[dict[str, object]] = []
    unchecked: list[str] = []
    corrections: list[dict[str, object]] = []
    specifications: list[tuple[str, str, str | None, str | None]] = [
        (url, "link_available", None, None) for url in urls
    ]
    for fragment in text.splitlines():
        if not fragment.strip():
            continue
        fragment_urls = list(
            dict.fromkeys(_clean_url(m.group()) for m in _URL.finditer(fragment))
        )
        prose = _URL.sub("", fragment)
        # Markdown punctuation does not constitute an unverified assertion.
        if not re.search(r"\w", prose):
            continue
        covered = prose
        if len(fragment_urls) == 1 and _NEWS.search(prose) and not _PRICE.search(prose):
            specifications.append(
                (
                    fragment_urls[0],
                    "news",
                    None,
                    _linked_claim(fragment, fragment_urls[0]),
                )
            )
            unchecked.append(prose.strip()[:1000])
            continue
        asserted_now = (
            not _CONDITIONAL.search(prose)
            and "?" not in prose
            and not re.search(r"\b(?:19|20)\d{2}\b", prose)
            and not fragment.lstrip().startswith(">")
        )
        if len(fragment_urls) == 1 and asserted_now:
            url = fragment_urls[0]
            prices = list(_PRICE.finditer(prose))
            if len(prices) == 1 and not re.search(
                r"\b(?:da|from|circa|about)\s*$", prose[: prices[0].start()], re.I
            ):
                amount = prices[0].group(1) or prices[0].group(2)
                price_claim = amount.replace(",", ".") + " EUR"
                specifications.append(
                    (
                        url,
                        "product_price",
                        price_claim,
                        f"Prezzo dichiarato: {price_claim}",
                    )
                )
                covered = _PRICE.sub("", covered)
            negative = bool(_NEGATIVE.search(prose))
            positive = bool(_POSITIVE.search(_NEGATIVE.sub("", prose)))
            if negative != positive:
                specifications.append(
                    (
                        url,
                        "product_availability",
                        "false" if negative else "true",
                        "Disponibilità dichiarata: "
                        + ("non disponibile" if negative else "disponibile"),
                    )
                )
            if _DISCOUNT.search(prose):
                # Negated discount wording remains unhandled rather than inverted.
                if not re.search(
                    r"\b(?:non|not)\s+(?:è\s+|is\s+)?"
                    r"(?:in sconto|scontat[oa]|discounted|on sale)",
                    prose,
                    re.I,
                ):
                    specifications.append(
                        (url, "product_discount", "true", "Sconto dichiarato: sì")
                    )
                else:
                    unchecked.append(prose.strip()[:1000])
            residual = _BOILERPLATE.sub("", covered)
            if (
                re.search(r"\w", residual)
                or len(prices) > 1
                or negative == positive
                and (negative or positive)
            ):
                unchecked.append(prose.strip()[:1000])
            elif not any(
                spec[0] == url and spec[1] != "link_available"
                for spec in specifications
            ):
                # A link caption cannot be vouched for merely by loading the link.
                unchecked.append(prose.strip()[:1000])
        else:
            unchecked.append(prose.strip()[:1000])
    for url in urls:
        check_cancellation()
        try:
            recalled = store.recall(url=url, limit=50)
        except ValueError:
            continue
        for prior in recalled["claims"]:
            if prior["do_not_reuse_prior_assertion"]:
                corrections.append(
                    {
                        "url": url,
                        "claim_id": prior["claim_id"],
                        "claim_text": prior["result"]["claim_text"],
                        "rationale": (
                            "Correzione precedente da ricontrollare; "
                            "non riutilizzare l'affermazione."
                        ),
                    }
                )
    implicit_stock = "Disponibilità osservata del prodotto suggerito"
    observed_price = "Prezzo osservato senza un prezzo asserito"
    for url in urls:
        parts = urlsplit(url)
        if (parts.hostname or "").removeprefix("www.") in {
            "amazon.it",
            "amazon.com",
            "amazon.co.uk",
            "amazon.de",
            "amazon.fr",
            "amazon.es",
        } and re.search(r"/(?:dp|gp/product)/[A-Za-z0-9]{10}(?:/|$)", parts.path):
            planned = {kind for source, kind, _, _ in specifications if source == url}
            if "product_availability" not in planned:
                specifications.append(
                    (url, "product_availability", "true", implicit_stock)
                )
            if "product_price" not in planned:
                specifications.append((url, "product_price", None, observed_price))
    unique = list(dict.fromkeys(specifications))
    unique.sort(key=lambda spec: spec[1] == "link_available")
    if len(unique) > 6:
        unchecked.append(
            "Altre proprietà non controllate: limite di sei verifiche per messaggio."
        )

    def check_one(
        specification: tuple[str, str, str | None, str | None],
    ) -> dict[str, object]:
        url, kind, expected, context = specification
        try:
            check_cancellation()
            if kind == "news":
                result = _news_observation(
                    url, language, context, region["country"], cancellation_event
                )
            elif language is not None:
                result = verify_url(url, kind, expected, context, language=language)
            else:
                result = verify_url(url, kind, expected, context)
            result = replace(
                result,
                evidence=[
                    *result.evidence,
                    {
                        "provider": "user_preferences",
                        "country_hint": region["country"],
                        "language_hint": region["language"],
                        "not_location_proof": True,
                        "limitation": (
                            "Country is a declared preference, "
                            "not delivery confirmation."
                        ),
                    },
                ],
            )
            check_cancellation()
            saved = store.record(result, ttl_seconds=300)
            market = {
                "amazon.it": "IT",
                "amazon.com": "US",
                "amazon.co.uk": "GB",
                "amazon.de": "DE",
                "amazon.fr": "FR",
                "amazon.es": "ES",
            }.get((urlsplit(url).hostname or "").removeprefix("www."))
            region_warning = (
                "Il marketplace della fonte è diverso dal paese scelto. "
                "Disponibilità e prezzo nel tuo paese non sono confermati."
                if market is not None and market != region["country"]
                else None
            )
            return {
                "result": saved["result"],
                "flags": saved["flags"],
                "assertion_scope": saved["assertion_scope"],
                "claim_id": saved["claim_id"],
                "implicit_recommendation_check": context == implicit_stock,
                "observation_only": context == observed_price,
                "regional_context": {
                    **region,
                    "marketplace_country": market,
                    "warning": region_warning,
                    "limitation": (
                        "Preferenze dichiarate: non GPS né conferma di "
                        "consegna o prezzo personale."
                    ),
                },
            }
        except (ValueError, OSError):
            return {
                "result": {
                    "url": url,
                    "kind": kind,
                    "outcome": "ERROR",
                    "rationale": (
                        "La proprietà non ha potuto essere verificata in sicurezza."
                    ),
                },
                "flags": {
                    "usable_as_current_fact": False,
                    "recheck_required": True,
                },
            }

    with ThreadPoolExecutor(max_workers=3) as workers:
        checks.extend(workers.map(check_one, unique[:6]))
    check_cancellation()
    if any(
        isinstance(context := check.get("regional_context"), dict)
        and context.get("warning")
        for check in checks
    ):
        unchecked.append("Prezzi e disponibilità non confermati nel paese selezionato.")
    outcomes = [check["result"]["outcome"] for check in checks]  # type: ignore[index]
    if "CONTRADICTED" in outcomes:
        status = "CONTRADICTED"
    elif (
        checks
        and all(outcome == "SUPPORTED" for outcome in outcomes)
        and not unchecked
        and not corrections
    ):
        status = "SUPPORTED"
    elif "SUPPORTED" in outcomes and (
        unchecked or corrections or any(outcome != "SUPPORTED" for outcome in outcomes)
    ):
        status = "PARTIAL"
    elif checks or unchecked or corrections:
        status = "INCONCLUSIVE"
    else:
        status = "NO_CLAIMS"
    return {
        "status": status,
        "label": _LABELS[status],
        "checks": checks,
        "unchecked_claims": unchecked[:40],
        "prior_corrections": corrections[:40],
        "preferences": region,
        "checked_at": datetime.now(UTC).isoformat(),
        "limitation": "Il badge riguarda solo le proprietà esplicitamente controllate. "
        "Non certifica la verità dell'intero messaggio; fonti, account "
        "e disponibilità possono cambiare.",
    }


def _clean_url(value: str) -> str:
    return value.rstrip(".,;!?:")


def _linked_claim(fragment: str, url: str) -> str | None:
    """Select the nearby statement, keeping unrelated earlier sentences private."""
    match = next(
        (item for item in _URL.finditer(fragment) if _clean_url(item.group()) == url),
        None,
    )
    if match is None:
        return None
    before = fragment[: match.start()]
    after = fragment[match.end() :]
    if "?" in before + after:
        return None
    sentences = re.split(r"(?<=[.!?])\s+", before)
    meaningful = [
        sentence for sentence in sentences if len(re.findall(r"\w+", sentence)) >= 3
    ]
    nearby = meaningful[-1] if meaningful else before
    suffix = re.split(r"(?<=[.!?])\s+", after)[0]
    claim = " ".join(re.sub(r"[\[\]()<>*_]", " ", nearby + " " + suffix).split())
    return claim[:2000] if len(re.findall(r"\w+", claim)) >= 3 else None
