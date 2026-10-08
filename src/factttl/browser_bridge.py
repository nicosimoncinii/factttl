"""Authenticated loopback-only bridge for the FactTTL browser extension."""

from __future__ import annotations

import argparse
import hmac
import http.client
import json
import os
import re
import secrets
import sqlite3
import threading
import time
from concurrent.futures import CancelledError, Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, cast

from factttl.browser_product import offer_identity, validate_observations
from factttl.message_verifier import normalize_preferences, verify_message
from factttl.verification_store import VerificationStore

DEFAULT_ORIGIN = "chrome-extension://nfnnmjcbjidblifbdfkhbdiidgcjbiem"
MAX_BODY = 200000
JOB_TTL_SECONDS = 300
_NEWS_HEALTH_CACHE: dict[str, tuple[float, dict[str, object]]] = {}
_NEWS_HEALTH_LOCK = threading.Lock()


def _local_news_model_available(model: str) -> dict[str, object]:
    """Read /api/tags locally; availability is not a successful inference test.

    Endpoint and fields: https://docs.ollama.com/api/tags
    """
    result: dict[str, object] = {"ready": False, "status": "service_unavailable"}
    connection = http.client.HTTPConnection("127.0.0.1", 11434, timeout=2)
    deadline = time.monotonic() + 2
    try:
        connection.request(
            "GET",
            "/api/tags",
            headers={
                "Accept": "application/json",
                "Accept-Encoding": "identity",
                "Connection": "close",
            },
        )
        response = connection.getresponse()
        if (
            response.status != 200
            or "json" not in response.getheader("Content-Type", "").lower()
        ):
            return result
        if response.getheader("Content-Encoding", "identity").lower() not in {
            "",
            "identity",
        }:
            return result
        chunks: list[bytes] = []
        count = 0
        while count <= 262144:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return result
            if connection.sock is not None:
                connection.sock.settimeout(remaining)
            chunk = response.read1(min(8192, 262145 - count))
            if not chunk:
                break
            chunks.append(chunk)
            count += len(chunk)
        if count > 262144:
            return result
        value = json.loads(b"".join(chunks))
        models = value.get("models") if isinstance(value, dict) else None
        if not isinstance(models, list) or len(models) > 1000:
            return result
        target = model if ":" in model.rsplit("/", 1)[-1] else model + ":latest"
        for entry in models:
            if not isinstance(entry, dict):
                continue
            name = entry.get("name")
            if not isinstance(name, str) or name not in {model, target}:
                continue
            details = entry.get("details")
            if (
                isinstance(details, dict)
                and details.get("format") == "gguf"
                and not entry.get("remote_host")
                and not entry.get("remote_model")
                and "cloud" not in model.casefold()
            ):
                return {"ready": True, "status": "model_available"}
            return {"ready": False, "status": "local_model_required"}
        return {"ready": False, "status": "model_not_installed"}
    except (OSError, ValueError, http.client.HTTPException):
        return result
    finally:
        connection.close()


def news_engine_health(model: str | None) -> dict[str, object]:
    """Cache bounded local availability checks; no source text is submitted."""
    from factttl.engine_profile import engine_profile

    try:
        profile_name = engine_profile().name
    except ValueError:
        profile_name = "invalid"
    discovery = os.environ.get("FACTTTL_NEWS_DISCOVERY", "disabled")
    if discovery not in {"disabled", "bing"}:
        discovery = "invalid"
    base: dict[str, object] = {
        "kind": "ollama_local",
        "configured": bool(model),
        "model": model[:128] if model else None,
        "scope": "current_source_consistency",
        "inference_profile": profile_name,
        "discovery_provider": discovery,
        "discovery_sends_query": discovery == "bing",
        "limitation": (
            "Availability of a local model, not proof that inference succeeded."
        ),
    }
    if not model:
        return {**base, "ready": False, "status": "not_configured"}
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}", model):
        return {**base, "ready": False, "status": "invalid_model_name"}
    with _NEWS_HEALTH_LOCK:
        now = time.monotonic()
        cached = _NEWS_HEALTH_CACHE.get(model)
        if cached is None or now - cached[0] >= 30:
            status = _local_news_model_available(model)
            if len(_NEWS_HEALTH_CACHE) >= 8:
                _NEWS_HEALTH_CACHE.pop(next(iter(_NEWS_HEALTH_CACHE)))
            _NEWS_HEALTH_CACHE[model] = (time.monotonic(), status)
        else:
            status = cached[1]
        return {**base, **status}


@dataclass(slots=True)
class _Job:
    identifier: str
    created_at: float
    cancellation: threading.Event = field(default_factory=threading.Event)
    future: Future[dict[str, object]] | None = None


def create_bridge_server(
    store: VerificationStore,
    token: str,
    allowed_origin: str,
    *,
    host: str = "127.0.0.1",
    port: int = 8765,
) -> ThreadingHTTPServer:
    """Construct a bounded authenticated server; port zero supports local tests."""
    if host != "127.0.0.1":
        raise ValueError("the browser bridge may only bind to 127.0.0.1")
    if len(token) < 32:
        raise ValueError("token must have at least 32 characters")
    if not re.fullmatch(
        r"(?:chrome-extension://[a-p]{32}|moz-extension://"
        r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})",
        allowed_origin,
    ):
        raise ValueError(
            "allowed_origin must identify exactly one Chrome or Firefox extension"
        )
    slots = threading.BoundedSemaphore(2)
    job_slots = threading.BoundedSemaphore(4)
    jobs: dict[str, _Job] = {}
    jobs_lock = threading.Lock()
    workers = ThreadPoolExecutor(max_workers=2, thread_name_prefix="factttl-job")
    reaper_stop = threading.Event()

    def reap_jobs() -> None:
        """Called under jobs_lock: expired payloads never persist to disk."""
        now = time.monotonic()
        for key, job in list(jobs.items()):
            if now - job.created_at >= JOB_TTL_SECONDS:
                job.cancellation.set()
                if job.future is not None:
                    job.future.cancel()
                del jobs[key]
        finished = [
            key
            for key, job in jobs.items()
            if job.future is not None and job.future.done()
        ]
        for key in finished[:-64]:
            del jobs[key]

    class BridgeServer(ThreadingHTTPServer):
        def server_close(self) -> None:
            reaper_stop.set()
            with jobs_lock:
                for job in jobs.values():
                    job.cancellation.set()
                jobs.clear()
            workers.shutdown(wait=False, cancel_futures=True)
            super().server_close()

    def periodic_reap() -> None:
        while not reaper_stop.wait(5):
            with jobs_lock:
                reap_jobs()

    class Handler(BaseHTTPRequestHandler):
        server_version = "FactTTLBridge/0.0.1"

        def setup(self) -> None:
            super().setup()
            self.connection.settimeout(10)

        def log_message(self, format: str, *args: object) -> None:
            # Never put message text, source URLs or bearer credentials in logs.
            return

        def _origin_ok(self) -> bool:
            origin = self.headers.get("Origin")
            if origin is not None:
                return origin == allowed_origin
            return self.headers.get("X-FactTTL-Origin") == allowed_origin

        def _send(self, status: int, data: dict[str, Any]) -> None:
            encoded = json.dumps(data, ensure_ascii=False, allow_nan=False).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Connection", "close")
            if self.headers.get("Origin") == allowed_origin:
                self.send_header("Access-Control-Allow-Origin", allowed_origin)
                self.send_header("Vary", "Origin")
            self.end_headers()
            self.wfile.write(encoded)

        def _authenticated(self) -> bool:
            host_header = self.headers.get("Host", "")
            expected_host = (
                f"127.0.0.1:{cast(ThreadingHTTPServer, self.server).server_port}"
            )
            if host_header != expected_host or not self._origin_ok():
                self._send(403, {"error": "Host or extension origin rejected"})
                return False
            actual = self.headers.get("Authorization", "")
            if not hmac.compare_digest(actual, "Bearer " + token):
                self._send(401, {"error": "Authentication required"})
                return False
            return True

        def do_OPTIONS(self) -> None:
            # Browser preflight does not carry bearer auth; it grants no operation.
            valid_route = self.path in {
                "/verify",
                "/health",
                "/jobs",
                "/context",
            } or bool(re.fullmatch(r"/jobs/[A-Za-z0-9_-]{24}(?:/cancel)?", self.path))
            if not self._origin_ok() or not valid_route:
                self._send(403, {"error": "Origin rejected"})
                return
            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin", allowed_origin)
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header(
                "Access-Control-Allow-Headers",
                "Authorization, Content-Type, X-FactTTL-Origin",
            )
            self.send_header("Access-Control-Allow-Private-Network", "true")
            self.send_header("Vary", "Origin")
            self.send_header("Content-Length", "0")
            self.end_headers()

        def do_GET(self) -> None:
            if not self._authenticated():
                return
            if self.path == "/health":
                self._send(
                    200,
                    {
                        "status": "ready",
                        "service": "FactTTL",
                        "connection_scope": "browser_extension_local_service",
                        "protocol_version": 1,
                        "capabilities": [
                            "message_verification",
                            "local_correction_memory",
                        ],
                        "news_engine": news_engine_health(
                            os.environ.get("FACTTTL_NEWS_MODEL")
                        ),
                    },
                )
                return
            match = re.fullmatch(r"/jobs/([A-Za-z0-9_-]{24})", self.path)
            if not match:
                self._send(404, {"error": "Unknown route"})
                return
            with jobs_lock:
                reap_jobs()
                job = jobs.get(match[1])
            if job is None:
                self._send(404, {"error": "Unknown or expired job"})
            elif job.cancellation.is_set():
                self._send(
                    200,
                    {"id": job.identifier, "job_id": match[1], "status": "CANCELED"},
                )
            elif job.future is None or not job.future.done():
                self._send(
                    202, {"id": job.identifier, "job_id": match[1], "status": "PENDING"}
                )
            else:
                try:
                    result = job.future.result()
                    self._send(200, {"id": job.identifier, **result})
                except CancelledError:
                    self._send(200, {"id": job.identifier, "status": "CANCELED"})
                except Exception:
                    self._send(
                        200,
                        {
                            "id": job.identifier,
                            "status": "ERROR",
                            "label": "Verifica non disponibile",
                            "checks": [],
                        },
                    )

        def do_POST(self) -> None:
            if not self._authenticated():
                return
            cancel = re.fullmatch(r"/jobs/([A-Za-z0-9_-]{24})/cancel", self.path)
            if cancel:
                with jobs_lock:
                    reap_jobs()
                    job = jobs.get(cancel[1])
                    if job is not None:
                        job.cancellation.set()
                        if job.future is not None:
                            job.future.cancel()
                if job is None:
                    self._send(404, {"error": "Unknown or expired job"})
                else:
                    self._send(
                        200,
                        {
                            "id": job.identifier,
                            "job_id": cancel[1],
                            "status": "CANCELED",
                        },
                    )
                return
            if self.path not in {"/verify", "/jobs", "/context"}:
                self._send(404, {"error": "Unknown route"})
                return
            if self.headers.get("Transfer-Encoding") is not None:
                self._send(400, {"error": "Chunked requests are not accepted"})
                return
            try:
                length = int(self.headers.get("Content-Length", ""))
            except ValueError:
                self._send(411, {"error": "Content-Length required"})
                return
            if not 0 < length <= MAX_BODY:
                self._send(413, {"error": "Request body exceeds configured limit"})
                return
            if (
                self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
                != "application/json"
            ):
                # Consume an already authenticated small body before closing, so
                # Windows does not reset the socket before the 415 arrives.
                if length <= 8192:
                    self.rfile.read(length)
                self._send(415, {"error": "Content-Type must be application/json"})
                return
            if not slots.acquire(blocking=False):
                self._send(429, {"error": "Verification capacity reached; retry later"})
                return
            try:
                raw = self.rfile.read(length)
                if len(raw) != length:
                    self._send(400, {"error": "Incomplete request body"})
                    return
                data = json.loads(raw)
                if not isinstance(data, dict):
                    raise ValueError("request must be a JSON object")
                if self.path == "/context":
                    if set(data) - {"query", "urls", "limit"}:
                        raise ValueError("unknown context field")
                    context_query = data.get("query")
                    if not isinstance(context_query, str):
                        raise ValueError("context query must be a string")
                    self._send(
                        200,
                        store.context(
                            context_query, data.get("urls"), data.get("limit", 8)
                        ),
                    )
                    return
                identifier = data.get("id")
                if (
                    not isinstance(identifier, str)
                    or not identifier
                    or len(identifier) > 128
                ):
                    raise ValueError("id must contain 1 to 128 characters")
                text = data.get("text")
                links = data.get("links", [])
                if not isinstance(text, str) or not isinstance(links, list):
                    raise ValueError("text and links have invalid types")
                if (
                    len(text) > 20000
                    or len(links) > 20
                    or any(not isinstance(url, str) or len(url) > 4096 for url in links)
                ):
                    raise ValueError("message payload exceeds limits")
                preferences = normalize_preferences(data.get("preferences"))
                browser_observations = validate_observations(
                    data.get("browser_observations")
                )
                requested_products = {offer_identity(url) for url in links}
                if any(
                    offer_identity(str(record["url"])) not in requested_products
                    for record in browser_observations
                ):
                    raise ValueError("browser observation must match a requested link")
                browser_options: dict[str, Any] = (
                    {"browser_observations": browser_observations}
                    if browser_observations
                    else {}
                )
                if self.path == "/jobs":
                    if not job_slots.acquire(blocking=False):
                        self._send(429, {"error": "Job capacity reached; retry later"})
                        return
                    try:
                        job_id = secrets.token_urlsafe(18)
                        job = _Job(identifier=identifier, created_at=time.monotonic())
                        with jobs_lock:
                            reap_jobs()
                            job.future = workers.submit(
                                verify_message,
                                text,
                                links,
                                store,
                                cancellation_event=job.cancellation,
                                preferences=preferences,
                                **browser_options,
                            )
                            job.future.add_done_callback(
                                lambda future: job_slots.release()
                            )
                            jobs[job_id] = job
                    except BaseException:
                        job_slots.release()
                        raise
                    self._send(
                        202, {"id": identifier, "job_id": job_id, "status": "PENDING"}
                    )
                    return
                result = verify_message(
                    text, links, store, preferences=preferences, **browser_options
                )
                self._send(200, {"id": identifier, **result})
            except (ValueError, UnicodeError, TypeError):
                self._send(400, {"error": "Invalid JSON or message payload"})
            except (OSError, RuntimeError, sqlite3.Error):
                self._send(503, {"error": "Local verification unavailable"})
            finally:
                slots.release()

    server = BridgeServer((host, port), Handler)
    server.daemon_threads = True
    threading.Thread(
        target=periodic_reap, daemon=True, name="factttl-job-expiry"
    ).start()
    return server


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="factttl-browser")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--extension-origin", default=DEFAULT_ORIGIN)
    parser.add_argument("--verification-db", default=".factttl/verification.sqlite3")
    parser.add_argument("--config", default=".factttl/extension-config.json")
    parser.add_argument(
        "--news-model", help="optional already installed Ollama model; never downloads"
    )
    args = parser.parse_args(argv)
    if not 1 <= args.port <= 65535:
        parser.error("port must be between 1 and 65535")
    if args.news_model:
        if len(args.news_model) > 128:
            parser.error("news model name must contain at most 128 characters")
        os.environ["FACTTTL_NEWS_MODEL"] = args.news_model
    path = Path(args.config)
    token = secrets.token_urlsafe(32)
    try:
        previous = json.loads(path.read_text(encoding="utf-8"))
        if (
            isinstance(previous, dict)
            and previous.get("allowed_origin") == args.extension_origin
            and isinstance(previous.get("token"), str)
            and len(previous["token"]) >= 32
        ):
            token = previous["token"]
    except (OSError, ValueError):
        pass
    store = VerificationStore(Path(args.verification_db))
    server = create_bridge_server(store, token, args.extension_origin, port=args.port)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "base_url": f"http://127.0.0.1:{args.port}",
                "token": token,
                "allowed_origin": args.extension_origin,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    path.chmod(0o600)
    print(f"FactTTL browser bridge ready at http://127.0.0.1:{args.port}")
    print(f"Import local configuration in the extension: {path.resolve()}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
