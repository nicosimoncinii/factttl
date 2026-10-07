"""Durable evidence history and conservative reuse decisions in local SQLite."""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from contextlib import closing
from copy import deepcopy
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from factttl.verification import VerificationResult, parse_timestamp, validate_url


def _normalized_url(url: str) -> str:
    parsed = urlsplit(validate_url(url))
    host = (parsed.hostname or "").lower()
    if host in {"amazon.it", "www.amazon.it"} and (
        (parsed.scheme.lower() == "https" and parsed.port in {None, 443})
        or (parsed.scheme.lower() == "http" and parsed.port in {None, 80})
    ):
        # ASIN is the product identity within this marketplace. Slugs and
        # referral parameters must not hide a previously recorded correction.
        asin = re.search(r"/(?:dp|gp/product)/([A-Z0-9]{10})(?:/|$)", parsed.path, re.I)
        if asin:
            tracking = {
                "ref",
                "ref_",
                "tag",
                "linkcode",
                "creative",
                "creativeasin",
                "ascsubtag",
                "camp",
            }
            # Seller, variant and every unknown parameter retain their scope.
            query = urlencode(
                [
                    (key, value)
                    for key, value in parse_qsl(parsed.query, keep_blank_values=True)
                    if key.casefold() not in tracking
                ]
            )
            canonical = f"https://www.amazon.it/dp/{asin[1].upper()}"
            return canonical + (f"?{query}" if query else "")
    if ":" in host:
        host = f"[{host}]"
    if parsed.port is not None and (parsed.scheme.lower(), parsed.port) not in {
        ("http", 80),
        ("https", 443),
    }:
        host += f":{parsed.port}"
    return urlunsplit(
        (parsed.scheme.lower(), host, parsed.path or "/", parsed.query, "")
    )


def _claim_key(result: VerificationResult) -> str:
    # Separate assertions about the same article must retain separate corrections.
    identity = [
        _normalized_url(result.url),
        result.kind.strip().casefold(),
        " ".join((result.expected_value or "").split()).casefold(),
        " ".join((result.claim_text or "").split()).casefold(),
    ]
    return hashlib.sha256(json.dumps(identity, ensure_ascii=False).encode()).hexdigest()


class VerificationStore:
    """Each operation uses its own connection and a transaction for concurrent calls."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as db, db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS observations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    claim_id TEXT NOT NULL,
                    observed_at TEXT NOT NULL,
                    recorded_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    result_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS observations_claim
                    ON observations(claim_id, id);
                CREATE TABLE IF NOT EXISTS claims (
                    claim_id TEXT PRIMARY KEY,
                    url TEXT NOT NULL,
                    latest_id INTEGER NOT NULL REFERENCES observations(id),
                    blocked INTEGER NOT NULL DEFAULT 0,
                    last_contradicted_at TEXT
                );
            """)
            self._migrate_canonical_claims(db)

    def _migrate_canonical_claims(self, db: sqlite3.Connection) -> None:
        """Rekey earlier URL identities atomically, preserving all observations."""
        db.execute("BEGIN IMMEDIATE")
        if db.execute("PRAGMA user_version").fetchone()[0] >= 2:
            return
        rows = db.execute("""SELECT c.*, o.observed_at, o.result_json, o.expires_at
            FROM claims c JOIN observations o ON o.id=c.latest_id""").fetchall()
        groups: dict[str, list[sqlite3.Row]] = {}
        for row in rows:
            result = VerificationResult(**json.loads(row["result_json"]))
            groups.setdefault(_claim_key(result), []).append(row)
        now = datetime.now(UTC)
        for claim_id, group in groups.items():
            for row in group:
                db.execute(
                    "UPDATE observations SET claim_id=? WHERE claim_id=?",
                    (claim_id, row["claim_id"]),
                )
                db.execute("DELETE FROM claims WHERE claim_id=?", (row["claim_id"],))
            latest = max(
                group,
                key=lambda row: (parse_timestamp(row["observed_at"]), row["latest_id"]),
            )
            contradictions = [
                parse_timestamp(row["last_contradicted_at"])
                for row in group
                if row["last_contradicted_at"]
            ]
            last_contradicted = max(contradictions) if contradictions else None
            blocked = any(row["blocked"] for row in group)
            result = json.loads(latest["result_json"])
            observed = parse_timestamp(latest["observed_at"])
            if (
                result["outcome"] == "SUPPORTED"
                and observed <= now < parse_timestamp(latest["expires_at"])
                and (last_contradicted is None or observed > last_contradicted)
                and any(
                    item.get("provider")
                    in {"live_public_web", "ai_assessed_live_source"}
                    for item in result["evidence"]
                )
            ):
                blocked = False
            db.execute(
                """INSERT INTO claims
                (claim_id, url, latest_id, blocked, last_contradicted_at)
                VALUES (?, ?, ?, ?, ?)""",
                (
                    claim_id,
                    _normalized_url(result["url"]),
                    latest["latest_id"],
                    int(blocked),
                    last_contradicted.isoformat() if last_contradicted else None,
                ),
            )
        db.execute("PRAGMA user_version=2")

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.db_path, timeout=15)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA busy_timeout=15000")
        return db

    def record(
        self, result: VerificationResult, ttl_seconds: int = 300
    ) -> dict[str, Any]:
        """Append evidence; inconclusive observations never erase a contradiction."""
        if not isinstance(result, VerificationResult):
            raise TypeError("result must be a VerificationResult")
        # Revalidate because callers can mutate the dictionaries inside a frozen result.
        result = replace(result, evidence=deepcopy(result.evidence))
        if result.outcome == "SUPPORTED" and not any(
            item.get("provider") in {"live_public_web", "ai_assessed_live_source"}
            for item in result.evidence
        ):
            raise ValueError("SUPPORTED requires evidence from a live source provider")
        if (
            isinstance(ttl_seconds, bool)
            or not isinstance(ttl_seconds, int)
            or not 0 <= ttl_seconds <= 2592000
        ):
            raise ValueError("ttl_seconds must be an integer between 0 and 2592000")
        now = datetime.now(UTC)
        observed = parse_timestamp(result.observed_at)
        if observed > now + timedelta(seconds=60):
            raise ValueError("an observation cannot be in the future")
        expires = observed + timedelta(seconds=ttl_seconds)
        claim_id = _claim_key(result)
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            existing = db.execute(
                """SELECT c.*, o.observed_at FROM claims c
                JOIN observations o ON o.id=c.latest_id WHERE c.claim_id=?""",
                (claim_id,),
            ).fetchone()
            cursor = db.execute(
                """INSERT INTO observations
                (claim_id, observed_at, recorded_at, expires_at, result_json)
                VALUES (?, ?, ?, ?, ?)""",
                (
                    claim_id,
                    observed.isoformat(),
                    now.isoformat(),
                    expires.isoformat(),
                    json.dumps(result.as_dict(), allow_nan=False, ensure_ascii=False),
                ),
            )
            observation_id = cursor.lastrowid
            if existing is None or observed >= parse_timestamp(existing["observed_at"]):
                blocked = bool(existing["blocked"]) if existing else False
                contradicted_at = existing["last_contradicted_at"] if existing else None
                if result.outcome == "CONTRADICTED":
                    blocked, contradicted_at = True, observed.isoformat()
                elif (
                    result.outcome == "SUPPORTED"
                    and observed <= now
                    and expires > now
                    and (
                        contradicted_at is None
                        or observed > parse_timestamp(contradicted_at)
                    )
                ):
                    # Reinstatement requires a newer observation with fresh evidence.
                    blocked = False
                db.execute(
                    """INSERT INTO claims
                    (claim_id, url, latest_id, blocked, last_contradicted_at)
                    VALUES (?, ?, ?, ?, ?) ON CONFLICT(claim_id) DO UPDATE SET
                    url=excluded.url, latest_id=excluded.latest_id,
                    blocked=excluded.blocked,
                    last_contradicted_at=excluded.last_contradicted_at""",
                    (
                        claim_id,
                        _normalized_url(result.url),
                        observation_id,
                        int(blocked),
                        contradicted_at,
                    ),
                )
            elif result.outcome == "CONTRADICTED":
                current = db.execute(
                    "SELECT result_json, expires_at FROM observations WHERE id=?",
                    (existing["latest_id"],),
                ).fetchone()
                # An older correction still matters after an inconclusive newer attempt.
                # A newer explicit supporting observation already supersedes it.
                if json.loads(current["result_json"])["outcome"] != "SUPPORTED":
                    prior = existing["last_contradicted_at"]
                    last = max(observed, parse_timestamp(prior)) if prior else observed
                    db.execute(
                        "UPDATE claims SET blocked=1, last_contradicted_at=? "
                        "WHERE claim_id=?",
                        (last.isoformat(), claim_id),
                    )
            return self._view(db, claim_id, now)

    def _view(
        self, db: sqlite3.Connection, claim_id: str, now: datetime
    ) -> dict[str, Any]:
        row = db.execute(
            """SELECT c.*, o.expires_at, o.result_json FROM claims c
            JOIN observations o ON o.id=c.latest_id WHERE c.claim_id=?""",
            (claim_id,),
        ).fetchone()
        if row is None:
            raise RuntimeError("stored claim is missing")
        result = json.loads(row["result_json"])
        supported = result["outcome"] == "SUPPORTED" and not row["blocked"]
        fresh = (
            parse_timestamp(result["observed_at"])
            <= now
            < parse_timestamp(row["expires_at"])
        )
        history_rows = db.execute(
            """SELECT result_json, recorded_at, expires_at FROM observations
            WHERE claim_id=? ORDER BY id DESC LIMIT 20""",
            (claim_id,),
        ).fetchall()
        count = db.execute(
            "SELECT COUNT(*) FROM observations WHERE claim_id=?", (claim_id,)
        ).fetchone()[0]
        flags = {
            "usable_as_current_fact": bool(supported and fresh),
            "recheck_required": not bool(supported and fresh),
            "do_not_reuse_prior_assertion": bool(row["blocked"]),
        }
        semantic_news = result["kind"] == "news" and any(
            item.get("provider") == "ai_assessed_live_source"
            and item.get("scope") == "current_source_consistency"
            for item in result["evidence"]
        )
        claim_target = result["kind"] == "claim" or semantic_news
        return {
            "claim_id": claim_id,
            "result": result,
            "expires_at": row["expires_at"],
            "evaluated_at": now.isoformat(),
            "flags": flags,
            **flags,
            "assessment_scope": (
                "source-relative evidence; not a guarantee of universal truth"
            ),
            "assertion_scope": {
                "property": result["kind"],
                "expected_value": result["expected_value"],
                "claim_text_is_context_only": not claim_target,
                "assessment_scope": "current_source_consistency"
                if semantic_news
                else None,
                "limitation": (
                    "The outcome assesses the selected property and expectation; "
                    "context text is not an independently verified assertion."
                    if not claim_target
                    else "The exact claim is assessed relative to the recorded "
                    "source or user report; universal truth is not guaranteed."
                ),
            },
            "independently_verified": result["outcome"] == "SUPPORTED"
            and not any(
                item.get("provider") == "ai_assessed_live_source"
                for item in result["evidence"]
            )
            and any(
                item.get("provider") == "live_public_web" for item in result["evidence"]
            ),
            "source_fetched_independently": any(
                item.get("provider") in {"live_public_web", "ai_assessed_live_source"}
                for item in result["evidence"]
            ),
            "history_count": count,
            "history_truncated": count > 20,
            "history": [
                {
                    "result": json.loads(item["result_json"]),
                    "recorded_at": item["recorded_at"],
                    "expires_at": item["expires_at"],
                }
                for item in history_rows
            ],
        }

    def recall(
        self, url: str | None = None, query: str | None = None, limit: int = 10
    ) -> dict[str, Any]:
        """Search saved observations before reusing a prior assertion."""
        if (
            isinstance(limit, bool)
            or not isinstance(limit, int)
            or not 1 <= limit <= 50
        ):
            raise ValueError("limit must be an integer between 1 and 50")
        if query is not None and (
            not isinstance(query, str) or not query.strip() or len(query) > 256
        ):
            raise ValueError("query must contain between 1 and 256 characters")
        conditions: list[str] = []
        params: list[object] = []
        if url is not None:
            conditions.append("c.url=?")
            params.append(_normalized_url(url))
        if query is not None:
            escaped = (
                query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            )
            conditions.append(
                "EXISTS (SELECT 1 FROM observations h WHERE h.claim_id=c.claim_id "
                "AND h.result_json LIKE ? ESCAPE '\\')"
            )
            params.append(f"%{escaped}%")
        where = " WHERE " + " AND ".join(conditions) if conditions else ""
        now = datetime.now(UTC)
        with closing(self._connect()) as db, db:
            # The count and returned decisions share a consistent read snapshot.
            db.execute("BEGIN")
            total = db.execute(
                "SELECT COUNT(*) FROM claims c" + where, params
            ).fetchone()[0]
            rows = db.execute(
                "SELECT c.claim_id FROM claims c"
                + where
                + " ORDER BY c.latest_id DESC LIMIT ?",
                [*params, limit],
            ).fetchall()
            return {
                "claims": [self._view(db, row["claim_id"], now) for row in rows],
                "total": total,
                "evaluated_at": now.isoformat(),
            }

    def close(self) -> None:
        """Connections close after every operation; provided for lifecycle callers."""


Store = VerificationStore
