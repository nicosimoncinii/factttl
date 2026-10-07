"""Network-free acceptance checks for live observations and fetch isolation."""

from __future__ import annotations

import json
import socket
import ssl

import pytest

from factttl import web_verifier as web

URL = "https://merchant.example/product"


def serve(monkeypatch: pytest.MonkeyPatch, html: str, status: int = 200) -> None:
    monkeypatch.setattr(
        web, "_fetch", lambda url: (URL, status, "text/html", html.encode())
    )


def product(offers: object) -> str:
    data = {"@type": "Product", "offers": offers}
    return '<script type="application/ld+json">' + json.dumps(data) + "</script>"


def offer(**values: object) -> dict[str, object]:
    return {"@type": "Offer", **values}


@pytest.mark.parametrize(
    "address",
    [
        "127.0.0.1",
        "10.0.0.1",
        "172.16.0.1",
        "192.168.1.2",
        "169.254.169.254",
        "0.0.0.0",
        "224.0.0.1",
        "::1",
        "fc00::1",
        "fe80::1",
        "::ffff:127.0.0.1",
    ],
)
def test_nonpublic_dns_rejected(monkeypatch: pytest.MonkeyPatch, address: str) -> None:
    monkeypatch.setattr(web, "_resolve", lambda host: [(2, 1, 6, "", (address, 443))])
    with pytest.raises(web.UnsafeURL):
        web._destination(URL)


@pytest.mark.parametrize(
    "url",
    [
        "http://example.com",
        "https://user:pass@example.com",
        "https://example.com:8443",
        "https://example.com/\r\nx",
    ],
)
def test_unsafe_url_rejected_before_dns(
    monkeypatch: pytest.MonkeyPatch, url: str
) -> None:
    def resolve(host: str) -> object:
        pytest.fail("Unsafe URL should not resolve DNS")

    monkeypatch.setattr(web, "_resolve", resolve)
    with pytest.raises(web.UnsafeURL):
        web._destination(url)


def test_mixed_public_private_dns_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        web,
        "_resolve",
        lambda host: [
            (2, 1, 6, "", ("8.8.8.8", 443)),
            (2, 1, 6, "", ("127.0.0.1", 443)),
        ],
    )
    with pytest.raises(web.UnsafeURL):
        web._destination(URL)


def test_https_connection_pins_address_but_validates_original_host(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[object] = []

    class Context:
        def wrap_socket(self, raw: object, *, server_hostname: str) -> object:
            calls.append(server_hostname)
            return raw

    class RawSocket:
        def settimeout(self, timeout: float) -> None:
            assert 0 < timeout <= web.TIMEOUT_SECONDS

    def create_socket(address: object, timeout: object) -> RawSocket:
        calls.append(address)
        return RawSocket()

    monkeypatch.setattr(socket, "create_connection", create_socket)
    monkeypatch.setattr(ssl, "create_default_context", lambda: Context())
    web._PinnedHTTPSConnection("merchant.example", "8.8.8.8").connect()
    assert calls == [("8.8.8.8", 443), "merchant.example"]


def test_redirect_to_private_ip_is_not_connected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connections: list[str] = []
    monkeypatch.setattr(
        web,
        "_resolve",
        lambda host: [
            (2, 1, 6, "", ("127.0.0.1" if host == "localhost" else "8.8.8.8", 443))
        ],
    )

    class Response:
        status = 302

        def getheader(self, name: str, default: str = "") -> str:
            return "https://localhost/secret" if name == "Location" else default

    class Connection:
        sock = None

        def __init__(self, host: str, address: str, timeout: float) -> None:
            connections.append(address)

        def request(self, *args: object, **kwargs: object) -> None:
            pass

        def getresponse(self) -> Response:
            return Response()

        def close(self) -> None:
            pass

    monkeypatch.setattr(web, "_PinnedHTTPSConnection", Connection)
    with pytest.raises(web.UnsafeURL):
        web._fetch(URL)
    assert connections == ["8.8.8.8"]


@pytest.mark.parametrize("status", [404, 410])
def test_missing_link_contradicted(
    monkeypatch: pytest.MonkeyPatch, status: int
) -> None:
    serve(monkeypatch, "missing", status)
    assert web.verify_url(URL, "link_available").outcome == "CONTRADICTED"
    assert web.verify_url(URL, "product_availability").outcome == "INCONCLUSIVE"


def test_200_is_not_product_availability(monkeypatch: pytest.MonkeyPatch) -> None:
    serve(monkeypatch, "<h1>Buy a great ESP32</h1>")
    assert web.verify_url(URL, "product_availability").outcome == "INCONCLUSIVE"


@pytest.mark.parametrize("status", [401, 403, 429, 503])
def test_blocked_not_false(monkeypatch: pytest.MonkeyPatch, status: int) -> None:
    serve(monkeypatch, "blocked", status)
    assert web.verify_url(URL, "product_availability").outcome == "INCONCLUSIVE"


def test_captcha_not_available(monkeypatch: pytest.MonkeyPatch) -> None:
    serve(
        monkeypatch,
        "<title>Robot Check</title>"
        + product(offer(availability="https://schema.org/InStock")),
    )
    assert web.verify_url(URL, "product_availability").outcome == "INCONCLUSIVE"


@pytest.mark.parametrize(
    "availability,outcome",
    [
        ("InStock", "SUPPORTED"),
        ("OutOfStock", "CONTRADICTED"),
        ("PreOrder", "INCONCLUSIVE"),
    ],
)
def test_explicit_stock(
    monkeypatch: pytest.MonkeyPatch, availability: str, outcome: str
) -> None:
    serve(
        monkeypatch, product(offer(availability="https://schema.org/" + availability))
    )
    assert web.verify_url(URL, "product_availability").outcome == outcome


def test_multiple_products_ambiguous(monkeypatch: pytest.MonkeyPatch) -> None:
    serve(monkeypatch, product(offer(availability="InStock")) * 2)
    assert web.verify_url(URL, "product_availability").outcome == "INCONCLUSIVE"


@pytest.mark.parametrize(
    "expected,outcome",
    [
        ("10 EUR", "SUPPORTED"),
        ("9 EUR", "CONTRADICTED"),
        ("10 USD", "INCONCLUSIVE"),
        (None, "INCONCLUSIVE"),
    ],
)
def test_price_comparison(
    monkeypatch: pytest.MonkeyPatch, expected: str | None, outcome: str
) -> None:
    serve(monkeypatch, product(offer(price="10.00", priceCurrency="EUR")))
    assert web.verify_url(URL, "product_price", expected).outcome == outcome


def test_expired_structured_price_not_current(monkeypatch: pytest.MonkeyPatch) -> None:
    serve(
        monkeypatch,
        product(offer(price="10", priceCurrency="EUR", priceValidUntil="2000-01-01")),
    )
    assert web.verify_url(URL, "product_price", "10 EUR").outcome == "INCONCLUSIVE"


def test_discount_requires_list_price(monkeypatch: pytest.MonkeyPatch) -> None:
    serve(monkeypatch, product(offer(price="10", priceCurrency="EUR")))
    assert web.verify_url(URL, "product_discount").outcome == "INCONCLUSIVE"


@pytest.mark.parametrize(
    "list_price,outcome", [("20", "SUPPORTED"), ("10", "CONTRADICTED")]
)
def test_discount_explicit_comparable_list_price(
    monkeypatch: pytest.MonkeyPatch, list_price: str, outcome: str
) -> None:
    serve(
        monkeypatch,
        product(
            offer(
                price="10",
                priceCurrency="EUR",
                priceSpecification={
                    "price": list_price,
                    "priceCurrency": "EUR",
                    "priceType": "https://schema.org/ListPrice",
                },
            )
        ),
    )
    assert web.verify_url(URL, "product_discount").outcome == outcome


def test_news_age_not_truth(monkeypatch: pytest.MonkeyPatch) -> None:
    serve(
        monkeypatch,
        '<meta property="article:published_time" content="2020-01-01T12:00:00Z">',
    )
    result = web.verify_url(URL, "news")
    assert result.published_at == "2020-01-01T12:00:00+00:00"
    assert result.outcome == "INCONCLUSIVE"


def test_live_quote_preserves_caller_assessment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    serve(monkeypatch, "<p>The old offer\n has ended.</p>")
    result = web.verify_claim_evidence(
        URL,
        "The offer is active",
        "The old offer has ended.",
        "CONTRADICTED",
        "The source says the offer ended",
    )
    assert result.outcome == "CONTRADICTED"
    assert result.evidence[-1]["provider"] == "ai_assessed_live_source"
    assert "not proof" in result.rationale


@pytest.mark.parametrize(
    "wrapper",
    [
        "<script>{}</script>",
        "<style>{}</style>",
        "<div hidden>{}</div>",
        '<div aria-hidden="true">{}</div>',
        '<div style="display: none">{}</div>',
    ],
)
def test_hidden_quote_cannot_anchor_claim(
    monkeypatch: pytest.MonkeyPatch, wrapper: str
) -> None:
    serve(monkeypatch, wrapper.format("The offer has ended.") + "<p>Other text</p>")
    result = web.verify_claim_evidence(
        URL,
        "The offer is active",
        "The offer has ended.",
        "CONTRADICTED",
        "Offer ended",
    )
    assert result.outcome == "INCONCLUSIVE"


def test_quote_missing_does_not_confirm_claim(monkeypatch: pytest.MonkeyPatch) -> None:
    serve(monkeypatch, "<p>No relevant evidence</p>")
    result = web.verify_claim_evidence(
        URL, "A claim", "Different quote", "SUPPORTED", "An assessment"
    )
    assert result.outcome == "INCONCLUSIVE"


def test_redirect_preserves_original_memory_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    serve(monkeypatch, "<p>This URL works</p>")
    requested = "https://merchant.example/old-link"
    result = web.verify_url(requested, "link_available")
    assert result.url == requested
    assert result.evidence[0]["url"] == URL


def test_captcha_quote_not_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    serve(monkeypatch, "<title>Robot Check</title><p>The offer ended.</p>")
    result = web.verify_claim_evidence(
        URL, "The offer is active", "The offer ended.", "CONTRADICTED", "Offer ended"
    )
    assert result.outcome == "INCONCLUSIVE"


def test_oversized_claim_rejected_before_fetch(monkeypatch: pytest.MonkeyPatch) -> None:
    def fetch(url: str) -> object:
        pytest.fail("Invalid input must not fetch")

    monkeypatch.setattr(web, "_fetch", fetch)
    with pytest.raises(ValueError, match="4000"):
        web.verify_url(URL, "news", claim_text="x" * 4001)


def test_oversized_response_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(web, "MAX_BYTES", 8)
    monkeypatch.setattr(web, "_resolve", lambda host: [(2, 1, 6, "", ("8.8.8.8", 443))])

    class Response:
        status = 200

        def getheader(self, name: str, default: str = "") -> str:
            return "text/html" if name == "Content-Type" else default

        def read1(self, size: int) -> bytes:
            return b"x" * size

    class Connection:
        sock = None

        def __init__(self, *args: object) -> None:
            pass

        def request(self, *args: object, **kwargs: object) -> None:
            pass

        def getresponse(self) -> Response:
            return Response()

        def close(self) -> None:
            pass

    monkeypatch.setattr(web, "_PinnedHTTPSConnection", Connection)
    with pytest.raises(ValueError, match="2 MiB"):
        web._fetch(URL)


@pytest.mark.parametrize(
    "status,outcome", [(200, "CONTRADICTED"), (404, "SUPPORTED"), (410, "SUPPORTED")]
)
def test_negative_link_expectation(
    monkeypatch: pytest.MonkeyPatch, status: int, outcome: str
) -> None:
    serve(monkeypatch, "<p>A page</p>", status)
    assert web.verify_url(URL, "link_available", "false").outcome == outcome


def test_multiple_seller_offers_remain_ambiguous(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    serve(
        monkeypatch,
        product(
            [
                offer(availability="InStock", url="https://seller1.example"),
                offer(availability="InStock", url="https://seller2.example"),
            ]
        ),
    )
    assert web.verify_url(URL, "product_availability").outcome == "INCONCLUSIVE"


def test_accept_language_header_is_fixed_and_validated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, str] = {}
    monkeypatch.setattr(web, "_resolve", lambda host: [(2, 1, 6, "", ("8.8.8.8", 443))])

    class Response:
        status = 200
        read = False

        def getheader(self, name: str, default: str = "") -> str:
            return "text/html" if name == "Content-Type" else default

        def read1(self, size: int) -> bytes:
            if self.read:
                return b""
            self.read = True
            return b"<p>Source</p>"

    class Connection:
        sock = None

        def __init__(self, *args: object) -> None:
            pass

        def request(self, method: str, path: str, *, headers: dict[str, str]) -> None:
            captured.update(headers)

        def getresponse(self) -> Response:
            return Response()

        def close(self) -> None:
            pass

    monkeypatch.setattr(web, "_PinnedHTTPSConnection", Connection)
    web._fetch(URL, language="de")
    assert captured["Accept-Language"] == "de"
    with pytest.raises(ValueError, match="language"):
        web._fetch(URL, language="it\r\nBadHeader:x")


AMAZON_URL = "https://www.amazon.it/dp/B0DKF9NCN1"


def amazon_page(
    stock: str = "Disponibilità immediata",
    price: str = "10,99€",
    reference: str | None = None,
    asin: str = "B0DKF9NCN1",
) -> str:
    basis = (
        '<span class="basisPrice"><span class="a-price a-text-price">'
        f'<span class="a-offscreen">{reference}</span></span></span>'
        if reference is not None
        else ""
    )
    return (
        f'<link rel="canonical" href="https://www.amazon.it/dp/{asin}">'
        f'<input id="ASIN" value="{asin}">'
        f'<div id="availability"><span>{stock}</span></div>'
        f'<div id="corePrice_feature_div" data-csa-c-asin="{asin}">'
        '<span class="a-price apex-pricetopay-value">'
        f'<span class="a-offscreen">{price}</span></span>{basis}</div>'
    )


def serve_amazon(monkeypatch: pytest.MonkeyPatch, html: str) -> None:
    monkeypatch.setattr(
        web,
        "_fetch",
        lambda url: (AMAZON_URL, 200, "text/html;charset=UTF-8", html.encode()),
    )


@pytest.mark.parametrize(
    "stock,outcome",
    [
        ("Disponibilità immediata", "SUPPORTED"),
        ("Attualmente non disponibile.", "CONTRADICTED"),
        ("Non disponibile", "CONTRADICTED"),
        ("Verifica la consegna per la tua zona", "INCONCLUSIVE"),
    ],
)
def test_amazon_explicit_stock_box(
    monkeypatch: pytest.MonkeyPatch, stock: str, outcome: str
) -> None:
    serve_amazon(monkeypatch, amazon_page(stock=stock))
    result = web.verify_url(AMAZON_URL, "product_availability")
    assert result.outcome == outcome
    assert "without login" in result.rationale


def test_amazon_wrong_product_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    serve_amazon(monkeypatch, amazon_page(asin="B000000000"))
    assert web.verify_url(AMAZON_URL, "product_availability").outcome == "INCONCLUSIVE"


def test_amazon_sponsored_prices_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
    html = amazon_page() + (
        '<div id="recommendations"><span class="a-price">'
        '<span class="a-offscreen">1,00€</span></span></div>'
    )
    serve_amazon(monkeypatch, html)
    result = web.verify_url(AMAZON_URL, "product_price", "1 EUR")
    assert result.outcome == "CONTRADICTED"
    assert result.observed_value == "10.99 EUR"


def test_amazon_generic_stock_text_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
    html = (
        amazon_page(stock="Select delivery location") + "<p>Disponibilità immediata</p>"
    )
    serve_amazon(monkeypatch, html)
    assert web.verify_url(AMAZON_URL, "product_availability").outcome == "INCONCLUSIVE"


@pytest.mark.parametrize(
    "reference,outcome",
    [("20,00€", "SUPPORTED"), ("10,99€", "CONTRADICTED"), (None, "INCONCLUSIVE")],
)
def test_amazon_discount_requires_scoped_reference(
    monkeypatch: pytest.MonkeyPatch, reference: str | None, outcome: str
) -> None:
    serve_amazon(monkeypatch, amazon_page(reference=reference))
    assert web.verify_url(AMAZON_URL, "product_discount").outcome == outcome


def test_amazon_duplicate_conflicting_stock_boxes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    html = amazon_page() + '<div id="availability">Attualmente non disponibile</div>'
    serve_amazon(monkeypatch, html)
    assert web.verify_url(AMAZON_URL, "product_availability").outcome == "INCONCLUSIVE"


def test_amazon_adapter_does_not_accept_lookalike_domain(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    serve_amazon(monkeypatch, amazon_page())
    result = web.verify_url(
        "https://www.amazon.it.attacker.example/dp/B0DKF9NCN1", "product_availability"
    )
    assert result.outcome == "INCONCLUSIVE"


def test_read_source_evidence_is_bounded_untrusted_live_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    serve(
        monkeypatch,
        "<title>A source</title><script>bad instructions</script><p>"
        + "x" * 13000
        + "</p>",
    )
    result = web.read_source_evidence(URL)
    assert result["status"] == "FETCHED"
    assert result["title"] == "A source"
    assert len(str(result["source_text"])) == 12000
    assert result["truncated"] is True
    assert "bad instructions" not in str(result["source_text"])


def test_read_source_evidence_blocks_captcha(monkeypatch: pytest.MonkeyPatch) -> None:
    serve(monkeypatch, "<title>Robot Check</title><p>Potential misleading evidence</p>")
    result = web.read_source_evidence(URL)
    assert result["status"] == "INCONCLUSIVE"
    assert result["source_text"] == ""


def test_page_parser_many_chunks_retains_bounded_text() -> None:
    parser = web._PageParser()
    for _ in range(5000):
        parser.feed("<span>A short chunk.</span>")
    assert parser.text.count("A short chunk.") == 5000
