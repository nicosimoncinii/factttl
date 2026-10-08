"""Discovery never trusts RSS snippets and never uploads full private text."""

from __future__ import annotations

import time
from typing import Any

import pytest

from factttl import source_discovery as discovery

CLAIM = "Notizia: NASA ha annunciato il nuovo lancio Artemis domani."


@pytest.fixture(autouse=True)
def clean_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    discovery._CACHE.clear()


def feed(urls: list[str]) -> bytes:
    return (
        "<rss><channel>"
        + "".join(
            "<item><title>NASA Artemis Fake decisive snippet</title><link>"
            + url
            + "</link><description>Never proof</description></item>"
            for url in urls
        )
        + "</channel></rss>"
    ).encode()


def test_public_search_only_returns_urls_and_caches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = []

    def fetch(url: str, **kwargs: Any) -> tuple[str, int, str, bytes]:
        calls.append((url, kwargs))
        return (
            url,
            200,
            "text/xml",
            feed(
                [
                    "https://publisher.example/article",
                    "https://127.0.0.1/private",
                    "https://publisher.example/article",
                ]
            ),
        )

    monkeypatch.setattr(discovery, "_fetch", fetch)
    result = discovery.discover_sources(CLAIM)
    assert result["urls"] == ["https://publisher.example/article"]
    assert "Fake decisive snippet" not in str(result)
    assert calls[0][1]["allowed_hosts"] == frozenset({"bing.com", "www.bing.com"})
    assert result["query_sent"] is True
    again = discovery.discover_sources(CLAIM)
    assert again["query_sent"] is False
    assert len(calls) == 1
    result["urls"].append("changed")
    assert discovery.discover_sources(CLAIM)["urls"] == [
        "https://publisher.example/article"
    ]


@pytest.mark.parametrize(
    "claim",
    [
        "Notizia: il mio appuntamento è alle ore nove domani.",
        "Notizia: Mario scrive a mario@example.com il dodici ottobre.",
        "Notizia: il server è disponibile su https://localhost/private.",
        "Notizia: chiama il numero +39 333 123 4567 per informazioni.",
        "Notizia: il token sk-abcde12345 è stato aggiornato oggi.",
        "Notizia: " + "x" * 500,
    ],
)
def test_sensitive_or_unbounded_claim_not_sent(
    claim: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        discovery, "_fetch", lambda *a, **k: pytest.fail("Private input sent")
    )
    result = discovery.discover_sources(claim)
    assert result["status"] == "PRIVACY_REJECTED"
    assert result["query_sent"] is False


@pytest.mark.parametrize(
    "body",
    [
        b'<!DOCTYPE rss [<!ENTITY bad "unsafe">]><rss/>',
        b"<rss><channel>",
        b"x" * (256 * 1024 + 1),
        '<!DOCTYPE rss [<!ENTITY bad "unsafe">]><rss/>'.encode("utf-16"),
    ],
    ids=["entity", "malformed", "oversize", "utf16-entity"],
)
def test_untrusted_xml_is_bounded(body: bytes, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        discovery, "_fetch", lambda url, **kw: (url, 200, "text/xml", body)
    )
    assert discovery.discover_sources(CLAIM)["status"] == "ERROR"


def test_ten_candidates_max(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        discovery,
        "_fetch",
        lambda url, **kw: (
            url,
            200,
            "text/xml",
            feed([f"https://publisher.example/{i}" for i in range(30)]),
        ),
    )
    urls = discovery.discover_sources(CLAIM)["urls"]
    assert isinstance(urls, list) and len(urls) == 10


def test_cache_expires(monkeypatch: pytest.MonkeyPatch) -> None:
    now = [0.0]
    monkeypatch.setattr(time, "monotonic", lambda: now[0])
    monkeypatch.setattr(
        discovery,
        "_fetch",
        lambda url, **kw: (url, 200, "text/xml", feed(["https://publisher.example/a"])),
    )
    discovery.discover_sources(CLAIM)
    now[0] = 301
    assert discovery.discover_sources(CLAIM)["query_sent"] is True


def test_country_language_change_query_context(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []

    def fetch(url: str, **kw: Any) -> tuple[str, int, str, bytes]:
        calls.append(url)
        return url, 200, "text/xml", feed([])

    monkeypatch.setattr(discovery, "_fetch", fetch)
    discovery.discover_sources(CLAIM, country="IT", language="it")
    discovery.discover_sources(CLAIM, country="US", language="en")
    assert len(calls) == 2  # Separate context caches; region is only a hint.
