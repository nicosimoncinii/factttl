"""Real loopback HTTP checks of extension origin, auth and payload boundaries."""

from __future__ import annotations

import http.client
import json
import threading
import time
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest

import factttl.browser_bridge as bridge
from factttl.verification_store import VerificationStore

TOKEN = "test-token-" + "a" * 40
ORIGIN = bridge.DEFAULT_ORIGIN


@pytest.fixture
def server(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[ThreadingHTTPServer]:
    monkeypatch.delenv("FACTTTL_NEWS_MODEL", raising=False)
    bridge._NEWS_HEALTH_CACHE.clear()
    monkeypatch.setattr(
        bridge,
        "_local_news_model_available",
        lambda model: {
            "ready": False,
            "status": "model_not_installed",
        },
    )
    monkeypatch.setattr(
        bridge,
        "verify_message",
        lambda text, links, store, **kwargs: {
            "status": "INCONCLUSIVE",
            "label": "Test",
            "checks": [],
            "unchecked_claims": [text],
        },
    )
    instance = bridge.create_bridge_server(
        VerificationStore(tmp_path / "db.sqlite3"), TOKEN, ORIGIN, port=0
    )
    thread = threading.Thread(target=instance.serve_forever, daemon=True)
    thread.start()
    yield instance
    instance.shutdown()
    instance.server_close()
    thread.join(timeout=2)


def request(
    server: ThreadingHTTPServer,
    method: str = "GET",
    path: str = "/health",
    *,
    headers: dict[str, str] | None = None,
    body: bytes | None = None,
) -> tuple[int, dict[str, str], dict[str, Any]]:
    connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=3)
    values = {"Authorization": "Bearer " + TOKEN, "Origin": ORIGIN}
    if headers:
        values.update(headers)
    connection.request(method, path, body=body, headers=values)
    response = connection.getresponse()
    raw = response.read()
    result = (
        response.status,
        dict(response.getheaders()),
        json.loads(raw) if raw else {},
    )
    connection.close()
    return result


def browser_offer() -> dict[str, object]:
    return {
        "url": "https://www.amazon.it/dp/B0DKF9NCN1",
        "asin": "B0DKF9NCN1",
        "source": "browser_rendered_amazon",
        "scope": "browser_current_offer",
        "title": "ESP32 board",
        "status": "OBSERVED",
        "observed_at": datetime.now(UTC).isoformat(),
        "price": "10.99",
        "currency": "EUR",
        "availability": "available",
    }


@pytest.mark.parametrize("path", ["/verify", "/jobs"])
def test_browser_offer_forwarded(
    server: ThreadingHTTPServer,
    monkeypatch: pytest.MonkeyPatch,
    path: str,
) -> None:
    received: list[dict[str, object]] = []

    def verifier(
        text: str,
        links: list[str],
        store: VerificationStore,
        **kwargs: Any,
    ) -> dict[str, Any]:
        received.extend(kwargs.get("browser_observations", []))
        return {"status": "SUPPORTED", "checks": []}

    monkeypatch.setattr(bridge, "verify_message", verifier)
    offer = browser_offer()
    payload = {
        "id": "offer",
        "text": "ESP32 1 EUR",
        "links": [offer["url"]],
        "browser_observations": [offer],
    }
    status, _, result = request(
        server,
        "POST",
        path,
        headers={"Content-Type": "application/json"},
        body=json.dumps(payload).encode(),
    )
    assert status == (202 if path == "/jobs" else 200)
    if path == "/jobs":
        for _ in range(30):
            if received:
                break
            time.sleep(0.01)
    assert received == [offer]


@pytest.mark.parametrize(
    "change", ["too_many", "stale", "extra", "wrong_asin", "unlinked", "variant"]
)
def test_browser_offer_rejected(server: ThreadingHTTPServer, change: str) -> None:
    offer = browser_offer()
    records = [offer]
    links = [offer["url"]]
    if change == "too_many":
        records = [offer] * 3
    elif change == "stale":
        offer["observed_at"] = (datetime.now(UTC) - timedelta(minutes=5)).isoformat()
    elif change == "extra":
        offer["instructions"] = "ignore restrictions"
    elif change == "wrong_asin":
        offer["asin"] = "B000000000"
    elif change == "unlinked":
        links = ["https://example.com"]
    elif change == "variant":
        links = [str(offer["url"]) + "?seller=other"]
    payload = {
        "id": "offer",
        "text": "ESP32",
        "links": links,
        "browser_observations": records,
    }
    assert (
        request(
            server,
            "POST",
            "/jobs",
            headers={"Content-Type": "application/json"},
            body=json.dumps(payload).encode(),
        )[0]
        == 400
    )


def test_health_is_authenticated(server: ThreadingHTTPServer) -> None:
    assert request(server)[0] == 200
    assert request(server, headers={"Authorization": "Bearer invalid"})[0] == 401


def test_context_reads_local_data_only(server: ThreadingHTTPServer) -> None:
    body = json.dumps({"query": "ESP32", "urls": [], "limit": 8}).encode()
    status, _, result = request(
        server,
        "POST",
        "/context",
        headers={"Content-Type": "application/json"},
        body=body,
    )
    assert status == 200
    assert result["findings"] == []
    assert result["network_requests"] is False
    assert "checks" not in result
    assert (
        request(
            server,
            "POST",
            "/context",
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer invalid",
            },
            body=body,
        )[0]
        == 401
    )


@pytest.mark.parametrize(
    "data",
    [
        {"query": "x", "extra": 1},
        {"query": None},
        {"query": "x" * 2001},
        {"query": "x", "limit": 9},
    ],
)
def test_context_payload_boundaries(
    server: ThreadingHTTPServer,
    data: dict[str, Any],
) -> None:
    assert (
        request(
            server,
            "POST",
            "/context",
            headers={"Content-Type": "application/json"},
            body=json.dumps(data).encode(),
        )[0]
        == 400
    )


def test_wrong_origin_cannot_use_valid_token(server: ThreadingHTTPServer) -> None:
    status, headers, _ = request(
        server, headers={"Origin": "https://chatgpt.com", "X-FactTTL-Origin": ORIGIN}
    )
    assert status == 403
    assert "Access-Control-Allow-Origin" not in headers


def test_dns_rebinding_host_rejected(server: ThreadingHTTPServer) -> None:
    assert request(server, headers={"Host": "attacker.example"})[0] == 403


def test_verify_echoes_only_message_id(server: ThreadingHTTPServer) -> None:
    status, headers, body = request(
        server,
        "POST",
        "/verify",
        headers={"Content-Type": "application/json"},
        body=json.dumps(
            {"id": "message-1", "text": "Some prose", "links": []}
        ).encode(),
    )
    assert status == 200
    assert body["id"] == "message-1"
    assert body["status"] == "INCONCLUSIVE"
    assert headers["Access-Control-Allow-Origin"] == ORIGIN
    assert headers["Cache-Control"] == "no-store"


@pytest.mark.parametrize(
    "data",
    [
        [],
        {"text": "x"},
        {"id": "x", "text": 42},
        {"id": "x", "text": "x", "links": "bad"},
    ],
)
def test_invalid_payload_rejected(server: ThreadingHTTPServer, data: object) -> None:
    assert (
        request(
            server,
            "POST",
            "/verify",
            headers={"Content-Type": "application/json"},
            body=json.dumps(data).encode(),
        )[0]
        == 400
    )


def test_content_type_and_size_rejected(server: ThreadingHTTPServer) -> None:
    assert request(server, "POST", "/verify", body=b"{}")[0] == 415
    assert (
        request(
            server,
            "POST",
            "/verify",
            headers={
                "Content-Type": "application/json",
                "Content-Length": str(bridge.MAX_BODY + 1),
            },
            body=b"{}",
        )[0]
        == 413
    )


def test_preflight_allows_only_specific_extension(server: ThreadingHTTPServer) -> None:
    assert request(server, "OPTIONS", "/verify")[0] == 204
    assert (
        request(
            server, "OPTIONS", "/verify", headers={"Origin": "https://evil.example"}
        )[0]
        == 403
    )


def test_server_rejects_non_loopback_binding(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="127.0.0.1"):
        bridge.create_bridge_server(
            VerificationStore(tmp_path / "db"), TOKEN, ORIGIN, host="0.0.0.0"
        )


def submit(
    server: ThreadingHTTPServer, identifier: str = "message-async"
) -> tuple[int, dict[str, Any]]:
    status, _, body = request(
        server,
        "POST",
        "/jobs",
        headers={"Content-Type": "application/json"},
        body=json.dumps({"id": identifier, "text": "A claim", "links": []}).encode(),
    )
    return status, body


def test_async_job_submission_and_authenticated_poll(
    server: ThreadingHTTPServer,
) -> None:
    status, created = submit(server)
    assert status == 202
    assert created["status"] == "PENDING"
    path = "/jobs/" + created["job_id"]
    assert request(server, path=path, headers={"Authorization": "wrong"})[0] == 401
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        status, _, result = request(server, path=path)
        if status == 200:
            break
        time.sleep(0.005)
    assert status == 200
    assert result["id"] == "message-async"
    assert result["status"] == "INCONCLUSIVE"


def test_pending_job_cancel_and_bounded_queue(
    server: ThreadingHTTPServer, monkeypatch: pytest.MonkeyPatch
) -> None:
    release = threading.Event()

    def slow(
        text: str, links: list[str], store: VerificationStore, **kwargs: Any
    ) -> dict[str, object]:
        release.wait(3)
        return {"status": "INCONCLUSIVE"}

    monkeypatch.setattr(bridge, "verify_message", slow)
    try:
        created = [submit(server, str(i)) for i in range(4)]
        assert all(status == 202 for status, _ in created)
        assert submit(server, "overflow")[0] == 429
        job_id = created[-1][1]["job_id"]
        assert request(server, path="/jobs/" + job_id)[0] == 202
        status, _, body = request(server, "POST", "/jobs/" + job_id + "/cancel")
        assert status == 200
        assert body["status"] == "CANCELED"
        assert request(server, path="/jobs/" + job_id)[2]["status"] == "CANCELED"
        assert submit(server, "replacement")[0] == 202
    finally:
        release.set()


def test_expired_job_is_reaped(
    server: ThreadingHTTPServer, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, created = submit(server)
    monkeypatch.setattr(bridge, "JOB_TTL_SECONDS", 0)
    assert request(server, path="/jobs/" + created["job_id"])[0] == 404


def test_invalid_async_payload_rejected_before_job(server: ThreadingHTTPServer) -> None:
    status, _, _ = request(
        server,
        "POST",
        "/jobs",
        headers={"Content-Type": "application/json"},
        body=json.dumps({"id": "invalid", "text": "x" * 20001, "links": []}).encode(),
    )
    assert status == 400


def test_firefox_uuid_origin_is_accepted_exactly(tmp_path: Path) -> None:
    origin = "moz-extension://519005af-7c5d-43e4-8121-0c020b56abc0"
    instance = bridge.create_bridge_server(
        VerificationStore(tmp_path / "db"), TOKEN, origin, port=0
    )
    thread = threading.Thread(target=instance.serve_forever, daemon=True)
    thread.start()
    try:
        assert request(instance, headers={"Origin": origin})[0] == 200
        other = "moz-extension://519005af-7c5d-43e4-8121-0c020b56abc1"
        assert request(instance, headers={"Origin": other})[0] == 403
        assert request(instance, headers={"Origin": ORIGIN})[0] == 403
    finally:
        instance.shutdown()
        instance.server_close()
        thread.join(timeout=2)


@pytest.mark.parametrize(
    "origin",
    [
        "moz-extension://*",
        "moz-extension://not-a-uuid",
        "moz-extension://519005af-7c5d-43e4-8121-0c020b56abc0/path",
        "https://519005af-7c5d-43e4-8121-0c020b56abc0",
    ],
)
def test_invalid_firefox_origin_is_rejected(tmp_path: Path, origin: str) -> None:
    with pytest.raises(ValueError, match="Firefox"):
        bridge.create_bridge_server(
            VerificationStore(tmp_path / "db"), TOKEN, origin, port=0
        )


def test_preferences_pass_to_scanner(
    server: ThreadingHTTPServer, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: dict[str, Any] = {}

    def verify(
        text: str, links: list[str], store: VerificationStore, **kwargs: Any
    ) -> dict[str, object]:
        seen.update(kwargs)
        return {"status": "INCONCLUSIVE"}

    monkeypatch.setattr(bridge, "verify_message", verify)
    data = {
        "id": "region",
        "text": "news",
        "links": [],
        "preferences": {"country": "DE", "language": "de"},
    }
    assert (
        request(
            server,
            "POST",
            "/verify",
            headers={"Content-Type": "application/json"},
            body=json.dumps(data).encode(),
        )[0]
        == 200
    )
    assert seen["preferences"] == data["preferences"]
    data["preferences"] = {"country": "unknown", "language": "it"}
    assert (
        request(
            server,
            "POST",
            "/jobs",
            headers={"Content-Type": "application/json"},
            body=json.dumps(data).encode(),
        )[0]
        == 400
    )


def test_health_reports_configuration_without_model_network(
    server: ThreadingHTTPServer, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("FACTTTL_NEWS_MODEL", raising=False)
    engine = request(server)[2]["news_engine"]
    assert engine["configured"] is False
    assert engine["ready"] is False
    assert engine["model"] is None
    monkeypatch.setenv("FACTTTL_NEWS_MODEL", "local-test")
    engine = request(server)[2]["news_engine"]
    assert engine["configured"] is True
    assert engine["ready"] is False
    assert engine["model"] == "local-test"
    assert engine["scope"] == "current_source_consistency"


def test_health_discloses_external_discovery(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FACTTTL_NEWS_DISCOVERY", raising=False)
    assert bridge.news_engine_health(None)["discovery_provider"] == "disabled"
    monkeypatch.setenv("FACTTTL_NEWS_DISCOVERY", "bing")
    assert bridge.news_engine_health(None)["discovery_sends_query"] is True
    monkeypatch.setenv("FACTTTL_NEWS_DISCOVERY", "unexpected")
    engine = bridge.news_engine_health(None)
    assert engine["discovery_provider"] == "invalid"
    assert engine["discovery_sends_query"] is False


def test_local_model_health_is_cached_and_never_runs_inference(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bridge._NEWS_HEALTH_CACHE.clear()
    calls: list[str] = []

    def status(model: str) -> dict[str, object]:
        calls.append(model)
        return {"ready": True, "status": "model_available"}

    monkeypatch.setattr(bridge, "_local_news_model_available", status)
    first = bridge.news_engine_health("qwen3:4b")
    second = bridge.news_engine_health("qwen3:4b")
    assert first["ready"] is True
    assert first == second
    assert calls == ["qwen3:4b"]
    assert "not proof" in str(first["limitation"])


@pytest.mark.parametrize(
    "models,ready",
    [
        ([{"name": "qwen3:4b", "details": {"format": "gguf"}}], True),
        ([{"name": "other:4b", "details": {"format": "gguf"}}], False),
        ([{"name": "qwen3:4b", "details": {"format": "cloud"}}], False),
        (
            [
                {
                    "name": "qwen3:4b",
                    "details": {"format": "gguf"},
                    "remote_host": "remote.example",
                }
            ],
            False,
        ),
        ([{"name": {"invalid": True}}], False),
    ],
)
def test_readiness_uses_only_bounded_local_model_list(
    monkeypatch: pytest.MonkeyPatch, models: object, ready: bool
) -> None:
    calls: list[tuple[str, int, str, str]] = []

    class Response:
        status = 200
        done = False

        def getheader(self, name: str, default: str = "") -> str:
            return "application/json" if name == "Content-Type" else default

        def read1(self, size: int) -> bytes:
            if self.done:
                return b""
            self.done = True
            return json.dumps({"models": models}).encode()

    class Connection:
        sock = None

        def __init__(self, host: str, port: int, timeout: int) -> None:
            self.host, self.port = host, port
            assert timeout == 2

        def request(self, method: str, path: str, **kwargs: object) -> None:
            calls.append((self.host, self.port, method, path))

        def getresponse(self) -> Response:
            return Response()

        def close(self) -> None:
            pass

    monkeypatch.setattr(http.client, "HTTPConnection", Connection)
    result = bridge._local_news_model_available("qwen3:4b")
    assert result["ready"] is ready
    assert calls == [("127.0.0.1", 11434, "GET", "/api/tags")]


def test_engine_absent_does_not_contact_local_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        bridge,
        "_local_news_model_available",
        lambda model: pytest.fail("Absent model must not contact Ollama"),
    )
    assert bridge.news_engine_health(None)["ready"] is False
