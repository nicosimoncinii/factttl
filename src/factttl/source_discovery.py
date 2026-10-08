"""Opt-in public news discovery: feed links are candidates, never evidence."""

from __future__ import annotations

import http.client
import ipaddress
import re
import time
import xml.etree.ElementTree as ET
from collections import OrderedDict
from threading import Lock
from urllib.parse import urlencode, urlsplit

from factttl.web_verifier import _fetch

_CACHE: OrderedDict[tuple[str, str, str], tuple[float, dict[str, object]]] = (
    OrderedDict()
)
_CACHE_LOCK = Lock()
_MAX_CACHE = 128
_MAX_FEED_BYTES = 256 * 1024
_COUNTRIES = {
    "IT": "it-IT",
    "US": "en-US",
    "GB": "en-GB",
    "DE": "de-DE",
    "FR": "fr-FR",
    "ES": "es-ES",
}
_PRIVATE = re.compile(
    r"(?:https?://|\b\S+@\S+\.\S+|\b(?:\d{1,3}\.){3}\d{1,3}\b|"
    r"\b(?:sk[-_]|Bearer\s|password|api[_ -]?key|token|secret|"
    r"localhost|confidential|confidenziale|privat[oa]|mio|mia|nostr[oa])\b|"
    r"(?:\+?\d[\s().-]*){9,})",
    re.I,
)
_STOP = frozenset(
    (
        "il lo la i gli le un una uno di del della dei delle e è a da in con per "
        "su che ha si non notizia notizie news articolo annuncia annunciato "
        "secondo fonte the an and of to in on is are has have at for from"
    ).split()
)


def _urls(value: object) -> list[str]:
    return (
        [url for url in value if isinstance(url, str)]
        if isinstance(value, list)
        else []
    )


def public_topic_query(claim: str) -> str | None:
    """Reject identifiable/sensitive strings; never upload a complete message.

    This is a conservative heuristic, not a guarantee of perfect PII detection.
    The feature must be explicitly enabled with its outbound-query disclosure.
    """
    if (
        not isinstance(claim, str)
        or not 15 <= len(claim) <= 400
        or _PRIVATE.search(claim)
    ):
        return None
    words = re.findall(r"[\wÀ-ÿ]+", claim)
    if not 4 <= len(words) <= 45 or any(len(word) > 35 for word in words):
        return None
    topics = [word for word in words if word.lower() not in _STOP]
    if len(topics) < 3:
        return None
    entities = [word for word in topics if any(char.isupper() for char in word)]
    # Grammar/operators from untrusted claims never become search operators.
    # Two named topic terms avoid an overconstrained cross-language AND query;
    # page reading/model comparison must still establish the entire claim.
    return " ".join(entities[:4] if len(entities) >= 2 else topics[:6])[:160]


def _candidate_url(url: str) -> bool:
    """Syntactic filter only; selected publisher reads must pin public DNS."""
    try:
        parts = urlsplit(url)
        host = (parts.hostname or "").lower()
        if (
            parts.scheme != "https"
            or not host
            or parts.username is not None
            or parts.password is not None
            or parts.port not in (None, 443)
            or host == "localhost"
            or host.endswith((".localhost", ".local", ".internal"))
            or "\\" in parts.netloc
            or "%" in host
            or any(ord(c) < 33 or ord(c) == 127 for c in url)
        ):
            return False
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            return "." in host
        return (
            address.is_global and not address.is_multicast and not address.is_reserved
        )
    except (ValueError, UnicodeError):
        return False


def discover_sources(
    claim: str, *, country: str = "IT", language: str = "it"
) -> dict[str, object]:
    """Discover at most ten public URLs, without fetching their page content."""
    base: dict[str, object] = {
        "provider": "bing_rss",
        "status": "PRIVACY_REJECTED",
        "urls": [],
        "candidate_count": 0,
        "query_sent": False,
        "limitation": (
            "RSS titles and snippets locate sources; they are not "
            "evidence. Domain diversity does not establish independence."
        ),
    }
    query = public_topic_query(claim)
    if (
        query is None
        or country not in _COUNTRIES
        or language not in {"it", "en", "de", "fr", "es"}
    ):
        return base
    key = (query, country, language)
    with _CACHE_LOCK:
        cached = _CACHE.get(key)
        if cached is not None and time.monotonic() - cached[0] < 300:
            _CACHE.move_to_end(key)
            return {
                **cached[1],
                "urls": _urls(cached[1]["urls"]),
                "query_sent": False,
                "cached": True,
            }
    url = "https://www.bing.com/search?" + urlencode(
        {
            "q": query,
            "format": "rss",
        }
    )
    result = {**base, "status": "ERROR", "query_sent": True}
    try:
        final_url, status, content_type, body = _fetch(
            url,
            language=language,
            allowed_hosts=frozenset({"www.bing.com", "bing.com"}),
        )
        if (
            urlsplit(final_url).hostname not in {"www.bing.com", "bing.com"}
            or status != 200
            or "xml" not in content_type.lower()
            or len(body) > _MAX_FEED_BYTES
        ):
            return result
        text = body.decode("utf-8", errors="strict")
        if "\x00" in text or re.search(r"<!\s*(?:DOCTYPE|ENTITY)\b", text, re.I):
            return result
        root = ET.fromstring(text)
        if root.tag != "rss":
            return result
        urls: list[str] = []
        for item in root.findall("./channel/item")[:10]:
            value = (item.findtext("link") or "").strip()
            if not value or len(value) > 4096:
                continue
            if not _candidate_url(value):
                continue
            # Feed text ranks candidates, but is never assessment evidence.
            terms = {term.casefold() for term in query.split() if len(term) >= 3}
            words = set(
                re.findall(
                    r"[\wÀ-ÿ]+",
                    (
                        item.findtext("title", "")
                        + " "
                        + item.findtext("description", "")
                        + " "
                        + value
                    ).casefold(),
                )
            )
            if len(terms & words) < min(2, len(terms)):
                continue
            if value not in urls:
                urls.append(value)
        result.update(
            status="FOUND" if urls else "EMPTY", urls=urls, candidate_count=len(urls)
        )
    except (OSError, ValueError, http.client.HTTPException, ET.ParseError):
        return result
    with _CACHE_LOCK:
        _CACHE[key] = (time.monotonic(), result)
        _CACHE.move_to_end(key)
        while len(_CACHE) > _MAX_CACHE:
            _CACHE.popitem(last=False)
    return {**result, "urls": _urls(result["urls"])}
