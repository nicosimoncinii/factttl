from datetime import UTC, datetime, timedelta

import pytest

from factttl.browser_product import (
    offer_identity,
    validate_observations,
    verify_browser_product,
)


def observation(**updates: object) -> dict[str, object]:
    record: dict[str, object] = {
        "url": "https://www.amazon.it/dp/B0DKF9NCN1",
        "asin": "B0DKF9NCN1",
        "observed_at": datetime.now(UTC).isoformat(),
        "source": "browser_rendered_amazon",
        "scope": "browser_current_offer",
        "status": "OBSERVED",
        "title": "ESP32 DevKit",
        "availability": "available",
        "price": "10.99",
        "currency": "EUR",
        "list_price": None,
    }
    return record | updates


def test_browser_price_matches_current_offer_and_explicit_message_claim() -> None:
    supported = verify_browser_product(
        observation(),
        "https://amazon.it/gp/product/B0DKF9NCN1?tag=example",
        "product_price",
        "10.99 EUR",
        "Prezzo dichiarato: 10.99 EUR",
    )
    assert supported.outcome == "SUPPORTED"
    assert supported.observed_value == "10.99 EUR"
    contradicted = verify_browser_product(
        observation(),
        str(observation()["url"]),
        "product_price",
        "9,99 EUR",
        "Prezzo dichiarato: 9.99 EUR",
    )
    assert contradicted.outcome == "CONTRADICTED"
    assert contradicted.evidence[0]["product_title"] == "ESP32 DevKit"


def test_unknown_variant_and_seller_parameters_never_share_offer_evidence() -> None:
    base = "https://amazon.it/dp/B0DKF9NCN1"
    assert offer_identity(base + "?tag=one&ref_=abc") == offer_identity(base)
    assert offer_identity(base + "?seller=A") != offer_identity(base + "?seller=B")
    assert offer_identity(base + "?th=1") != offer_identity(base)
    with pytest.raises(ValueError, match="does not match"):
        verify_browser_product(
            observation(url=base + "?seller=A"),
            base + "?seller=B",
            "product_price",
            "10.99 EUR",
            None,
        )


@pytest.mark.parametrize(
    "update",
    [
        {"observed_at": (datetime.now(UTC) - timedelta(minutes=3)).isoformat()},
        {"price": "10.999"},
        {"price": "10.99", "currency": None},
        {"title": ""},
        {"url": "https://user:secret@amazon.it/dp/B0DKF9NCN1"},
    ],
)
def test_invalid_observations_are_rejected(update: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        validate_observations([observation(**update)])


def test_unknown_stock_and_blocked_browser_are_not_supported() -> None:
    for update in ({"availability": "unknown"}, {"status": "BLOCKED"}):
        result = verify_browser_product(
            observation(**update),
            str(observation()["url"]),
            "product_availability",
            "true",
            None,
        )
        assert result.outcome == "INCONCLUSIVE"


def test_unsupported_currency_comparison_is_inconclusive() -> None:
    result = verify_browser_product(
        observation(), str(observation()["url"]), "product_price", "10.99 USD", None
    )
    assert result.outcome == "INCONCLUSIVE"
