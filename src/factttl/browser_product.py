"""Typed primary-offer observations from the user's Amazon browser session."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from decimal import Decimal
from urllib.parse import parse_qsl, urljoin, urlsplit

from factttl.verification import VerificationResult, parse_timestamp

_HOSTS = {
    "amazon.it",
    "amazon.com",
    "amazon.co.uk",
    "amazon.de",
    "amazon.fr",
    "amazon.es",
}
_MONEY = re.compile(r"\d{1,7}(?:\.\d{1,2})?\Z")
_TRACKING = {
    "ref",
    "ref_",
    "tag",
    "linkcode",
    "creative",
    "creativeasin",
    "camp",
    "ascsubtag",
}


def resolve_product_url(url: str) -> str | None:
    """Decode only bounded same-marketplace Amazon advertising wrappers.

    This is not a redirect fetcher: short links and arbitrary destinations remain
    unresolved. Unknown offer parameters on the selected product are preserved.
    """
    if not isinstance(url, str) or len(url) > 4096:
        return None
    current = url
    marketplace: str | None = None
    for _ in range(3):
        try:
            parts = urlsplit(current)
            host = (parts.hostname or "").removeprefix("www.")
            if (
                parts.scheme != "https"
                or parts.port not in {None, 443}
                or parts.username is not None
                or parts.password is not None
                or host not in _HOSTS
                or any(ord(char) < 32 for char in current)
                or "\\" in current
                or (marketplace is not None and host != marketplace)
            ):
                return None
            marketplace = host
            if re.search(
                r"/(?:dp|gp/product|gp/aw/d)/[A-Z0-9]{10}(?:[/.]|$)", parts.path, re.I
            ):
                return current
            if not (
                parts.path == "/sspa/click" or parts.path.startswith("/gp/slredirect/")
            ):
                return None
            targets = [value for key, value in parse_qsl(parts.query) if key == "url"]
            if len(targets) != 1 or not targets[0] or len(targets[0]) > 4096:
                return None
            current = urljoin(current, targets[0])
        except ValueError:
            return None
    return None


def offer_identity(url: str) -> tuple[str, str, tuple[tuple[str, str], ...]] | None:
    """Keep unknown offer/variant selectors; ignore only named tracking fields."""
    product = product_identity(url)
    if product is None:
        return None
    resolved = resolve_product_url(url)
    if resolved is None:
        return None
    query = tuple(
        sorted(
            (key, value)
            for key, value in parse_qsl(
                urlsplit(resolved).query, keep_blank_values=True
            )
            if key.lower() not in _TRACKING
        )
    )
    return *product, query


def product_identity(url: str) -> tuple[str, str] | None:
    try:
        resolved = resolve_product_url(url)
        if resolved is None:
            return None
        parts = urlsplit(resolved)
        host = (parts.hostname or "").removeprefix("www.")
        asin = re.search(
            r"/(?:dp|gp/product|gp/aw/d)/([A-Z0-9]{10})(?:[/.]|$)", parts.path, re.I
        )
        if (
            parts.scheme != "https"
            or parts.port not in (None, 443)
            or parts.username
            or parts.password
            or host not in _HOSTS
            or not asin
        ):
            return None
        return host, asin[1].upper()
    except ValueError:
        return None


def validate_observations(value: object) -> list[dict[str, object]]:
    if value is None:
        return []
    if not isinstance(value, list) or len(value) > 2:
        raise ValueError("At most two browser product observations")
    allowed = {
        "url",
        "asin",
        "observed_at",
        "source",
        "scope",
        "status",
        "title",
        "availability",
        "availability_text",
        "price",
        "currency",
        "list_price",
    }
    result: list[dict[str, object]] = []
    for record in value:
        if not isinstance(record, dict) or set(record) - allowed:
            raise ValueError("Invalid browser observation")
        if any(not isinstance(key, str) for key in record):
            raise ValueError("Invalid observation fields")
        url = record.get("url")
        identity = (
            product_identity(url) if isinstance(url, str) and len(url) <= 4096 else None
        )
        if (
            not identity
            or record.get("asin") != identity[1]
            or record.get("source") != "browser_rendered_amazon"
            or record.get("scope") != "browser_current_offer"
        ):
            raise ValueError("Invalid browser product identity")
        observed = record.get("observed_at")
        if not isinstance(observed, str):
            raise ValueError("Missing observation timestamp")
        age = (datetime.now(UTC) - parse_timestamp(observed)).total_seconds()
        if not -5 <= age <= 120:
            raise ValueError("Browser offer observation is stale")
        if record.get("status") not in {"OBSERVED", "BLOCKED", "WRONG_PRODUCT"}:
            raise ValueError("Invalid observation status")
        if record.get("availability", "unknown") not in {
            "available",
            "unavailable",
            "unknown",
        }:
            raise ValueError("Invalid stock")
        for key, limit in (("title", 180), ("availability_text", 300)):
            if key in record and (
                not isinstance(record[key], str) or len(record[key]) > limit
            ):
                raise ValueError("Oversized observation field")
        if (
            record.get("status") == "OBSERVED"
            and not str(record.get("title", "")).strip()
        ):
            raise ValueError("Observed product needs an identified title")
        for key in ("price", "list_price"):
            amount = record.get(key)
            if amount is not None and (
                not isinstance(amount, str)
                or not _MONEY.fullmatch(amount)
                or Decimal(amount) <= 0
            ):
                raise ValueError("Invalid price")
        if record.get("currency") not in {None, "EUR", "USD", "GBP"}:
            raise ValueError("Invalid currency")
        if (record.get("price") is None) != (record.get("currency") is None):
            raise ValueError("Price and currency must be paired")
        result.append(dict(record))
    return result


def verify_browser_product(
    observation: dict[str, object],
    url: str,
    kind: str,
    expected: str | None,
    claim: str | None,
) -> VerificationResult:
    if kind not in {"product_availability", "product_price", "product_discount"}:
        raise ValueError("Unsupported browser product property")
    observation = validate_observations([observation])[0]
    if offer_identity(str(observation["url"])) != offer_identity(url):
        raise ValueError("Observation does not match requested product")
    evidence = {
        "provider": "live_public_web",
        "source": "browser_rendered_amazon",
        "url": observation["url"],
        "scope": "browser_current_offer",
        "product_title": observation.get("title", ""),
        "observed_at": observation["observed_at"],
        "limitation": (
            "Primary offer displayed in the browser. Delivery destination "
            "and checkout total are not verified."
        ),
    }
    actual: str | None = None
    outcome = "INCONCLUSIVE"
    rationale = "La pagina non mostra un valore univoco per questa proprietà."
    if observation["status"] == "BLOCKED":
        rationale = (
            "Amazon chiede un controllo nel browser: apri il prodotto e completalo tu."
        )
    elif observation["status"] != "OBSERVED":
        rationale = "La pagina aperta non corrisponde al prodotto indicato."
    elif kind == "product_availability":
        stock = observation.get("availability", "unknown")
        if stock in {"available", "unavailable"}:
            actual = str(stock)
            evidence["availability"] = stock
            if expected in {"true", "false"}:
                agrees = (stock == "available") == (expected == "true")
                outcome = "SUPPORTED" if agrees else "CONTRADICTED"
            else:
                outcome = "SUPPORTED"
            rationale = (
                "Disponibilità letta nell'offerta principale aperta nel browser."
            )
    elif kind == "product_price" and observation.get("price"):
        currency = str(observation["currency"])
        amount = Decimal(str(observation["price"]))
        actual = f"{amount:.2f} {currency}"
        evidence.update(price=str(amount), currency=currency)
        if expected is None:
            outcome = "SUPPORTED"
        else:
            match = re.fullmatch(r"(\d+(?:[.,]\d+)?)\s+(EUR|USD|GBP)", expected)
            if match and match[2] == currency:
                outcome = (
                    "SUPPORTED"
                    if Decimal(match[1].replace(",", ".")) == amount
                    else "CONTRADICTED"
                )
        rationale = "Prezzo letto nell'offerta principale aperta nel browser."
    elif (
        kind == "product_discount"
        and observation.get("price")
        and observation.get("list_price")
    ):
        amount = Decimal(str(observation["price"]))
        reference = Decimal(str(observation["list_price"]))
        discounted = amount < reference
        actual = "discounted" if discounted else "not_discounted"
        evidence.update(
            price=str(amount),
            list_price=str(reference),
            currency=observation["currency"],
        )
        if expected in {"true", "false"}:
            outcome = (
                "SUPPORTED" if discounted == (expected == "true") else "CONTRADICTED"
            )
        rationale = (
            "Confronto tra prezzo attuale e riferimento mostrato da Amazon; "
            "non prova lo storico del prezzo."
        )
    return VerificationResult(
        url=url,
        kind=kind,
        outcome=outcome,
        expected_value=expected,
        claim_text=claim,
        observed_value=actual,
        observed_at=str(observation["observed_at"]),
        rationale=rationale,
        evidence=[evidence],
    )
