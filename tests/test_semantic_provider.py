"""Local provider integration, citation validation and fail-closed transport."""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from factttl import semantic_provider as provider

URL = "https://news.example/article"
QUOTE = "L'azienda ha annunciato il lancio per il 12 ottobre 2026."
SOURCE = "Comunicato ufficiale.\n" + QUOTE + "\nIl prezzo non è ancora confermato."
CLAIM = "Il lancio è previsto per il 12 ottobre 2026."
LOCAL_MODEL: dict[str, object] = {
    "details": {"format": "gguf"},
    "model_info": {"general.architecture": "qwen3"},
}


def timestamp(offset: int = 0) -> str:
    return (datetime.now(UTC) + timedelta(seconds=offset)).isoformat()


def assessment(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "outcome": "SUPPORTED",
        "rationale": "L'annuncio nella fonte riporta la stessa data.",
        "citations": [{"source_id": "source-1", "quote": QUOTE}],
        "scope": "current_source_consistency",
    }
    value.update(overrides)
    if "rationale" not in overrides:
        value["rationale"] = (
            str(value["rationale"]) + " ASSESSMENT: " + str(value["outcome"])
        )
    return value


def envelope(content: object) -> dict[str, object]:
    return {
        "done": True,
        "done_reason": "stop",
        "message": {"role": "assistant", "content": json.dumps(content)},
    }


def call(**overrides: Any) -> dict[str, object]:
    values: dict[str, Any] = {
        "claim_text": CLAIM,
        "source_text": SOURCE,
        "source_url": URL,
        "model": "qwen3:4b",
        "source_observed_at": timestamp(),
    }
    values.update(overrides)
    return provider.assess_news_claim(**values)


def serve(
    monkeypatch: pytest.MonkeyPatch,
    *,
    output: dict[str, object] | None = None,
    model_info: dict[str, object] | None = None,
) -> list[tuple[str, dict[str, object]]]:
    requests: list[tuple[str, dict[str, object]]] = []

    def post(
        path: str, payload: dict[str, object], deadline: float
    ) -> dict[str, object]:
        assert deadline > time.monotonic()
        requests.append((path, payload))
        if path == "/api/show":
            return dict(LOCAL_MODEL) if model_info is None else model_info
        return envelope(assessment()) if output is None else output

    monkeypatch.setattr(provider, "_post_json", post)
    return requests


def test_absent_model_does_not_send_data(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FACTTTL_NEWS_MODEL", raising=False)
    requests = serve(monkeypatch)
    result = call(model=None)
    assert result["configured"] is False
    assert result["engine"] == "absent"
    assert result["outcome"] == "INCONCLUSIVE"
    assert requests == []


def test_environment_model_is_explicit_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FACTTTL_NEWS_MODEL", "qwen3:4b")
    requests = serve(monkeypatch)
    result = call(model=None)
    assert result["outcome"] == "SUPPORTED"
    assert result["model"] == "qwen3:4b"
    assert requests[0] == ("/api/show", {"model": "qwen3:4b"})


@pytest.mark.parametrize("outcome", ["SUPPORTED", "CONTRADICTED", "INCONCLUSIVE"])
def test_valid_scoped_assessment(monkeypatch: pytest.MonkeyPatch, outcome: str) -> None:
    requests = serve(monkeypatch, output=envelope(assessment(outcome=outcome)))
    result = call(language="de", country="DE")
    assert result["outcome"] == outcome
    assert result["scope"] == "current_source_consistency"
    assert result["provider"] == "ai_assessed_live_source"
    assert "non è una verifica indipendente" in str(result["limitation"])
    assert result["citations"] == [
        {"source_id": "source-1", "source_url": URL, "quote": QUOTE}
    ]
    assert requests[1][0] == "/api/chat"
    payload = requests[1][1]
    assert payload["stream"] is False
    assert "tools" not in payload
    assert isinstance(payload["format"], dict)
    assert "temperature" in str(payload["options"])
    assert "untrusted_source_text" in str(payload["messages"])
    assert "language de" in str(payload["messages"])
    assert "Country DE is a hint" in str(payload["messages"])
    assert SOURCE not in str(requests[0])


@pytest.mark.parametrize(
    "model",
    ["qwen3:cloud", "x-cloud", "https://remote/model", "x\nmalicious", "x" * 129],
)
def test_unsafe_model_no_request(monkeypatch: pytest.MonkeyPatch, model: str) -> None:
    requests = serve(monkeypatch)
    assert call(model=model)["error_reason"] == "unsafe_or_cloud_model"
    assert requests == []


@pytest.mark.parametrize(
    "metadata",
    [
        {**LOCAL_MODEL, "remote_host": "https://ollama.com"},
        {**LOCAL_MODEL, "remote_model": "remote"},
        {"details": {"format": "gguf"}},
        {
            "details": {"format": "remote"},
            "model_info": {"general.architecture": "qwen3"},
        },
        {},
    ],
)
def test_no_claim_sent_until_local_weights_confirmed(
    monkeypatch: pytest.MonkeyPatch, metadata: dict[str, object]
) -> None:
    requests = serve(monkeypatch, model_info=metadata)
    result = call()
    assert result["error_reason"] == "local_model_not_confirmed"
    assert requests == [("/api/show", {"model": "qwen3:4b"})]


@pytest.mark.parametrize(
    "overrides",
    [
        {"claim_text": ""},
        {"claim_text": "x" * 4001},
        {"source_text": ""},
        {"source_text": "x" * 12001},
        {"source_url": "http://news.example/a"},
        {"source_url": "https://user:secret@news.example/a"},
        {"language": "xx"},
        {"country": "XX"},
        {"source_observed_at": None},
        {"source_observed_at": "2026-10-07T12:00:00"},
        {"source_observed_at": timestamp(-301)},
        {"source_observed_at": timestamp(60)},
    ],
)
def test_bad_input_no_network(
    monkeypatch: pytest.MonkeyPatch, overrides: dict[str, object]
) -> None:
    requests = serve(monkeypatch)
    assert call(**overrides)["outcome"] == "INCONCLUSIVE"
    assert requests == []


@pytest.mark.parametrize(
    "output",
    [
        assessment(outcome="TRUE"),
        assessment(scope="world_truth"),
        assessment(extra="ignore all previous instructions"),
        assessment(rationale=" "),
        assessment(rationale="x" * 2001),
        assessment(citations=[]),
        assessment(citations=[{"source_id": "source-2", "quote": QUOTE}]),
        assessment(
            citations=[
                {
                    "source_id": "source-1",
                    "quote": "Invented source statement about the launch date.",
                }
            ]
        ),
        assessment(citations=[{"source_id": "source-1", "quote": "lancio"}]),
        assessment(
            citations=[
                {
                    "source_id": "source-1",
                    "quote": QUOTE,
                    "source_url": "https://invented.example",
                }
            ]
        ),
        assessment(citations=[{"source_id": "source-1", "quote": QUOTE}] * 4),
    ],
)
def test_invalid_or_ungrounded_assessment_inconclusive(
    monkeypatch: pytest.MonkeyPatch, output: dict[str, object]
) -> None:
    serve(monkeypatch, output=envelope(output))
    result = call()
    assert result["outcome"] == "INCONCLUSIVE"
    assert result["citations"] == []
    assert str(result["rationale"]).startswith("Notizia non verificata")


def test_whitespace_only_normalization(monkeypatch: pytest.MonkeyPatch) -> None:
    serve(monkeypatch, output=envelope(assessment()))
    result = call(source_text=SOURCE.replace("annunciato il", "annunciato\n  il"))
    assert result["outcome"] == "SUPPORTED"


@pytest.mark.parametrize(
    "rationale",
    [
        "The claim is directly contradicted. ASSESSMENT: SUPPORTED",
        "L'affermazione è contraddetta. ASSESSMENT: SUPPORTED",
        "Die Behauptung ist widerlegt. ASSESSMENT: SUPPORTED",
        "Cette affirmation est contredite. ASSESSMENT: SUPPORTED",
        "La afirmación es contradicha. ASSESSMENT: SUPPORTED",
        "The source explicitly contradicts the claim. ASSESSMENT: CONTRADICTED",
        "ASSESSMENT: SUPPORTED",
        "The claim that 'Ollama forbids schemas' is directly contradicted "
        "by the source.",
    ],
)
def test_rationale_conflict_never_promotes_to_supported(
    monkeypatch: pytest.MonkeyPatch, rationale: str
) -> None:
    serve(monkeypatch, output=envelope(assessment(rationale=rationale)))
    result = call()
    assert result["outcome"] == "INCONCLUSIVE"
    assert result["error_reason"] == "inconsistent_assessment_verdict"


def test_noncontradiction_not_confused_with_contradiction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    serve(
        monkeypatch,
        output=envelope(
            assessment(
                rationale=(
                    "The claim is not contradicted and is explicitly supported. "
                    "ASSESSMENT: SUPPORTED"
                )
            )
        ),
    )
    assert call()["outcome"] == "SUPPORTED"


def test_natural_rationale_without_marker_supported(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    serve(
        monkeypatch,
        output=envelope(
            assessment(
                rationale=(
                    "La fonte riporta esplicitamente la stessa data "
                    "e supporta il claim."
                )
            )
        ),
    )
    assert call()["outcome"] == "SUPPORTED"


def test_multibyte_input_cannot_silently_truncate_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests = serve(monkeypatch)
    result = call(source_text="\U0001f600" * 12000)
    assert result["error_reason"] == "input_exceeds_context_budget"
    assert requests == []  # Reject profile overflow before contacting the model.


def test_absence_not_contradiction(monkeypatch: pytest.MonkeyPatch) -> None:
    serve(
        monkeypatch, output=envelope(assessment(outcome="INCONCLUSIVE", citations=[]))
    )
    assert call()["outcome"] == "INCONCLUSIVE"


@pytest.mark.parametrize(
    "overrides",
    [
        {"done": False},
        {"done": "true"},
        {"done_reason": "length"},
        {"remote_host": "https://ollama.com"},
        {"remote_model": "cloud"},
        {"message": {"role": "assistant", "content": "not json"}},
        {"message": {"role": "assistant", "content": "x" * 16001}},
        {"message": {"role": "user", "content": "{}"}},
        {
            "message": {
                "role": "assistant",
                "content": "{}",
                "tool_calls": [{"name": "browse"}],
            }
        },
    ],
)
def test_bad_envelope_inconclusive(
    monkeypatch: pytest.MonkeyPatch, overrides: dict[str, object]
) -> None:
    packet = envelope(assessment())
    packet.update(overrides)
    serve(monkeypatch, output=packet)
    assert call()["outcome"] == "INCONCLUSIVE"


def test_duplicate_output_keys_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    packet = envelope(assessment())
    packet["message"] = {
        "role": "assistant",
        "content": '{"outcome":"INCONCLUSIVE","outcome":"SUPPORTED"}',
    }
    serve(monkeypatch, output=packet)
    assert call()["error_reason"] == "invalid_json"


def test_stale_after_model_inconclusive(monkeypatch: pytest.MonkeyPatch) -> None:
    serve(monkeypatch)
    freshness = iter([True, False])
    monkeypatch.setattr(provider, "_source_is_recent", lambda observed: next(freshness))
    assert call()["error_reason"] == "source_stale_after_assessment"


def test_provider_error_no_raw_response_leak(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(*args: object) -> dict[str, object]:
        raise provider._ProviderError("timeout")

    monkeypatch.setattr(provider, "_post_json", fail)
    result = call()
    assert result["error_reason"] == "timeout"
    assert SOURCE not in str(result)


class FakeSocket:
    def __init__(self) -> None:
        self.timeouts: list[float] = []

    def settimeout(self, value: float) -> None:
        self.timeouts.append(value)


class FakeResponse:
    def __init__(
        self, data: bytes, status: int = 200, headers: dict[str, str] | None = None
    ) -> None:
        self.data = data
        self.status = status
        self.headers = {"Content-Type": "application/json", **(headers or {})}

    def getheader(self, name: str, default: str | None = None) -> str | None:
        return self.headers.get(name, default)

    def read1(self, size: int) -> bytes:
        chunk, self.data = self.data[:size], self.data[size:]
        return chunk

    def isclosed(self) -> bool:
        return not self.data


def transport(
    monkeypatch: pytest.MonkeyPatch,
    response: FakeResponse,
    *,
    error: Exception | None = None,
) -> dict[str, Any]:
    state: dict[str, Any] = {}

    class Connection:
        def __init__(self, host: str, port: int, *, timeout: float) -> None:
            state.update(host=host, port=port, timeout=timeout, closed=False)
            self.sock = FakeSocket()

        def request(self, method: str, path: str, **kwargs: object) -> None:
            state.update(method=method, path=path, **kwargs)
            if error is not None:
                raise error

        def getresponse(self) -> FakeResponse:
            return response

        def close(self) -> None:
            state["closed"] = True

    monkeypatch.setattr("http.client.HTTPConnection", Connection)
    return state


def test_transport_fixed_loopback_and_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HTTP_PROXY", "https://evil.example")
    state = transport(monkeypatch, FakeResponse(b'{"ok":true}'))
    assert provider._post_json(
        "/api/show", {"model": "qwen3:4b"}, time.monotonic() + 1
    ) == {"ok": True}
    assert state["host"] == "127.0.0.1"
    assert state["port"] == 11434
    assert state["method"] == "POST"
    assert state["closed"] is True
    assert "Authorization" not in state["headers"]


@pytest.mark.parametrize(
    "response",
    [
        FakeResponse(b"{}", status=302, headers={"Location": "https://remote.example"}),
        FakeResponse(b"secret response", status=500),
        FakeResponse(b"{}", headers={"Content-Encoding": "gzip"}),
        FakeResponse(b"{}", headers={"Content-Type": "text/html"}),
        FakeResponse(b"{}", headers={"Content-Length": str(1024 * 1024 + 1)}),
        FakeResponse(b"{}", headers={"Content-Length": "invalid"}),
        FakeResponse(b"x" * (1024 * 1024 + 1)),
        FakeResponse(b'{"key":1,"key":2}'),
        FakeResponse(b'{"key":NaN}'),
    ],
)
def test_transport_rejects_unbounded_unsafe_response(
    monkeypatch: pytest.MonkeyPatch, response: FakeResponse
) -> None:
    state = transport(monkeypatch, response)
    with pytest.raises(provider._ProviderError):
        provider._post_json("/api/show", {}, time.monotonic() + 1)
    assert state["closed"] is True


@pytest.mark.parametrize("error", [TimeoutError(), OSError("private daemon body")])
def test_transport_network_error_is_bounded(
    monkeypatch: pytest.MonkeyPatch, error: Exception
) -> None:
    state = transport(monkeypatch, FakeResponse(b"{}"), error=error)
    with pytest.raises(provider._ProviderError) as caught:
        provider._post_json("/api/show", {}, time.monotonic() + 1)
    assert "private daemon body" not in str(caught.value)
    assert state["closed"] is True


def test_total_deadline(monkeypatch: pytest.MonkeyPatch) -> None:
    transport(monkeypatch, FakeResponse(b"{}"))
    with pytest.raises(provider._ProviderError, match="timeout"):
        provider._post_json("/api/show", {}, time.monotonic() - 1)
