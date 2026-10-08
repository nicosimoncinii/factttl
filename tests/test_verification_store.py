"""Persistence retains corrections without pretending that age establishes truth."""

import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from factttl.verification import VerificationResult
from factttl.verification_store import VerificationStore


def observation(
    outcome: str = "SUPPORTED",
    *,
    age: int = 10,
    url: str = "https://example.com/product",
    claim: str = "Device is in stock",
    provider: str = "live_public_web",
) -> VerificationResult:
    return VerificationResult(
        url=url,
        kind="claim",
        outcome=outcome,
        observed_at=(datetime.now(UTC) - timedelta(seconds=age)).isoformat(),
        rationale="Observed a scoped source statement.",
        claim_text=claim,
        evidence=[{"provider": provider, "quote": "Scoped evidence"}],
    )


def test_history_persists_across_store_instances(tmp_path: Path) -> None:
    path = tmp_path / "memory.sqlite3"
    store = VerificationStore(path)
    first = store.record(observation())
    store.record(observation("CONTRADICTED", age=9))
    store.close()
    recalled = VerificationStore(path).recall(url="https://example.com/product")
    claim = recalled["claims"][0]
    assert claim["claim_id"] == first["claim_id"]
    assert claim["history_count"] == 2
    assert claim["history"][1]["result"]["outcome"] == "SUPPORTED"
    assert claim["do_not_reuse_prior_assertion"] is True
    assert claim["usable_as_current_fact"] is False


def test_expired_support_requires_recheck_not_false_verdict(tmp_path: Path) -> None:
    claim = VerificationStore(tmp_path / "memory.sqlite3").record(
        observation(age=600), ttl_seconds=30
    )
    assert claim["result"]["outcome"] == "SUPPORTED"
    assert claim["usable_as_current_fact"] is False
    assert claim["recheck_required"] is True
    assert claim["do_not_reuse_prior_assertion"] is False


@pytest.mark.parametrize("outcome", ["INCONCLUSIVE", "ERROR"])
def test_inconclusive_recheck_does_not_erase_correction(
    tmp_path: Path, outcome: str
) -> None:
    store = VerificationStore(tmp_path / "memory.sqlite3")
    store.record(observation("CONTRADICTED", age=10), ttl_seconds=0)
    latest = store.record(observation(outcome, age=9))
    assert latest["result"]["outcome"] == outcome
    assert latest["do_not_reuse_prior_assertion"] is True
    assert latest["usable_as_current_fact"] is False
    assert latest["recheck_required"] is True


def test_fresh_new_evidence_can_reinstate_assertion(tmp_path: Path) -> None:
    store = VerificationStore(tmp_path / "memory.sqlite3")
    store.record(observation("CONTRADICTED", age=10))
    latest = store.record(observation("SUPPORTED", age=9))
    assert latest["usable_as_current_fact"] is True
    assert latest["do_not_reuse_prior_assertion"] is False
    assert latest["history_count"] == 2


def test_old_support_cannot_reinstate_assertion(tmp_path: Path) -> None:
    store = VerificationStore(tmp_path / "memory.sqlite3")
    store.record(observation("CONTRADICTED", age=10))
    latest = store.record(observation("SUPPORTED", age=20))
    assert latest["result"]["outcome"] == "CONTRADICTED"
    assert latest["do_not_reuse_prior_assertion"] is True
    assert latest["history_count"] == 2


def test_user_correction_blocks_without_independent_truth_claim(tmp_path: Path) -> None:
    claim = VerificationStore(tmp_path / "memory.sqlite3").record(
        observation("CONTRADICTED", provider="user_report"), ttl_seconds=0
    )
    assert claim["do_not_reuse_prior_assertion"] is True
    assert claim["independently_verified"] is False
    assert "source-relative" in claim["assessment_scope"]


def test_no_reinstatement_from_expired_support(tmp_path: Path) -> None:
    store = VerificationStore(tmp_path / "memory.sqlite3")
    store.record(observation("CONTRADICTED", age=600))
    latest = store.record(observation("SUPPORTED", age=300), ttl_seconds=10)
    assert latest["do_not_reuse_prior_assertion"] is True
    assert latest["usable_as_current_fact"] is False


def test_normalized_identity_and_distinct_claims(tmp_path: Path) -> None:
    store = VerificationStore(tmp_path / "memory.sqlite3")
    first = store.record(observation(url="HTTPS://EXAMPLE.COM:443/product#one"))
    same = store.record(observation(claim=" Device  is in STOCK "))
    other = store.record(observation(claim="Device is on sale"))
    assert first["claim_id"] == same["claim_id"]
    assert other["claim_id"] != first["claim_id"]
    assert store.recall(url="https://example.com/product#two")["total"] == 2


def test_query_matches_historical_corrections_and_escapes_wildcards(
    tmp_path: Path,
) -> None:
    store = VerificationStore(tmp_path / "memory.sqlite3")
    correction = observation("CONTRADICTED", provider="user_report")
    correction.evidence[0]["correction"] = "discount was 20%"
    store.record(correction)
    store.record(observation("INCONCLUSIVE", age=9))
    assert store.recall(query="20%")["total"] == 1
    assert store.recall(query="20_")["total"] == 0


def test_parallel_writes_retain_every_observation(tmp_path: Path) -> None:
    path = tmp_path / "memory.sqlite3"
    VerificationStore(path)

    def write(_: int) -> None:
        VerificationStore(path).record(observation("CONTRADICTED"))

    with ThreadPoolExecutor(max_workers=6) as workers:
        list(workers.map(write, range(36)))
    claim = VerificationStore(path).recall()["claims"][0]
    assert claim["history_count"] == 36
    assert claim["history_truncated"] is True
    assert len(claim["history"]) == 20
    assert claim["do_not_reuse_prior_assertion"] is True


@pytest.mark.parametrize("ttl", [-1, True, 2592001, 1.5])
def test_invalid_ttl_is_rejected(tmp_path: Path, ttl: object) -> None:
    with pytest.raises(ValueError, match="ttl_seconds"):
        VerificationStore(tmp_path / "memory.sqlite3").record(
            observation(),
            ttl_seconds=ttl,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize("limit", [0, 51, True, "10"])
def test_invalid_recall_limit_is_rejected(tmp_path: Path, limit: object) -> None:
    with pytest.raises(ValueError, match="limit"):
        VerificationStore(tmp_path / "memory.sqlite3").recall(
            limit=limit  # type: ignore[arg-type]
        )


def test_future_observation_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="future"):
        VerificationStore(tmp_path / "memory.sqlite3").record(observation(age=-3600))


def test_fabricated_provider_cannot_support(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="live source"):
        VerificationStore(tmp_path / "memory.sqlite3").record(
            observation(provider="user_report")
        )


def test_definitive_result_requires_evidence() -> None:
    data = observation().as_dict()
    data["evidence"] = []
    with pytest.raises(ValueError, match="explicit evidence"):
        VerificationResult(**data)  # type: ignore[arg-type]


@pytest.mark.parametrize("url", ["file:///secret", "https://u:p@example.com", "x"])
def test_invalid_url_is_rejected(url: str) -> None:
    with pytest.raises(ValueError):
        observation(url=url)


def test_amazon_aliases_recall_same_product_correction(tmp_path: Path) -> None:
    store = VerificationStore(tmp_path / "memory.sqlite3")
    first = store.record(
        observation(
            "CONTRADICTED",
            provider="user_report",
            url="https://www.amazon.it/ESP32-Device/dp/B012345678/ref=sr_1?tag=first",
        )
    )
    aliases = [
        "https://amazon.it/gp/product/B012345678?tag=second",
        "https://www.amazon.it:443/dp/b012345678/other?ref=changed",
        "https://amazon.it/dp/B012345678",
    ]
    for alias in aliases:
        recalled = store.recall(url=alias)
        assert recalled["total"] == 1
        assert recalled["claims"][0]["claim_id"] == first["claim_id"]
        assert recalled["claims"][0]["do_not_reuse_prior_assertion"] is True


def test_amazon_different_asin_or_marketplace_is_separate(tmp_path: Path) -> None:
    store = VerificationStore(tmp_path / "memory.sqlite3")
    store.record(observation(url="https://amazon.it/dp/B012345678"))
    distinct = [
        "https://amazon.it/dp/B012345679",
        "https://www.amazon.de/dp/B012345678",
        "https://www.amazon.com/dp/B012345678",
        "https://amazon.it.evil.example/dp/B012345678",
    ]
    for url in distinct:
        assert store.recall(url=url)["total"] == 0


@pytest.mark.parametrize("marketplace", ["it", "de", "com", "co.uk", "fr", "es"])
def test_mobile_and_advertising_aliases_preserve_unavailable_offer_memory(
    tmp_path: Path, marketplace: str
) -> None:
    store = VerificationStore(tmp_path / "memory.sqlite3")
    direct = f"https://www.amazon.{marketplace}/dp/B012345678?seller=SellerA"
    store.record(observation("CONTRADICTED", provider="user_report", url=direct))
    aliases = [
        f"https://amazon.{marketplace}/gp/aw/d/B012345678?seller=SellerA&tag=new",
        f"https://www.amazon.{marketplace}/sspa/click?url=%2Fdp%2FB012345678%3Fseller%3DSellerA",
    ]
    for alias in aliases:
        recalled = store.recall(url=alias)
        assert recalled["total"] == 1
        assert recalled["claims"][0]["do_not_reuse_prior_assertion"] is True
    assert store.recall(url=direct.replace("SellerA", "SellerB"))["total"] == 0


def test_non_amazon_query_parameters_are_preserved(tmp_path: Path) -> None:
    store = VerificationStore(tmp_path / "memory.sqlite3")
    store.record(observation(url="https://merchant.example/product?variant=blue"))
    assert (
        store.recall(url="https://merchant.example/product?variant=blue")["total"] == 1
    )
    assert (
        store.recall(url="https://merchant.example/product?variant=red")["total"] == 0
    )


def test_amazon_seller_and_unknown_parameters_retain_scope(tmp_path: Path) -> None:
    store = VerificationStore(tmp_path / "memory.sqlite3")
    store.record(
        observation(url="https://amazon.it/dp/B012345678?smid=SELLER1&tag=first")
    )
    assert (
        store.recall(
            url="https://amazon.it/gp/product/B012345678?smid=SELLER1&tag=second"
        )["total"]
        == 1
    )
    assert (
        store.recall(url="https://amazon.it/dp/B012345678?smid=SELLER2")["total"] == 0
    )
    assert (
        store.recall(url="https://amazon.it/dp/B012345678?variant=blue")["total"] == 0
    )


def test_legacy_amazon_identity_migrates_without_losing_correction(
    tmp_path: Path,
) -> None:
    path = tmp_path / "memory.sqlite3"
    store = VerificationStore(path)
    original = "https://www.amazon.it/Device/dp/B012345678?tag=original"
    claim = store.record(
        observation("CONTRADICTED", url=original, provider="user_report")
    )
    store.record(observation("INCONCLUSIVE", url=original, age=9))
    with sqlite3.connect(path) as db:
        db.execute(
            "UPDATE observations SET claim_id='legacy' WHERE claim_id=?",
            (claim["claim_id"],),
        )
        db.execute(
            "UPDATE claims SET claim_id='legacy', url=? WHERE claim_id=?",
            (original, claim["claim_id"]),
        )
        db.execute("PRAGMA user_version=0")
    migrated = VerificationStore(path)
    recalled = migrated.recall(url="https://amazon.it/gp/product/B012345678?tag=new")
    assert recalled["total"] == 1
    assert recalled["claims"][0]["history_count"] == 2
    assert recalled["claims"][0]["do_not_reuse_prior_assertion"] is True
    appended = migrated.record(observation("ERROR", url=original, age=8))
    assert appended["history_count"] == 3
    assert appended["do_not_reuse_prior_assertion"] is True
    assert VerificationStore(path).recall()["claims"][0]["history_count"] == 3


def test_legacy_alias_merge_preserves_history_and_block(tmp_path: Path) -> None:
    path = tmp_path / "memory.sqlite3"
    store = VerificationStore(path)
    first = store.record(
        observation("CONTRADICTED", url="https://amazon.it/dp/B012345678?tag=one")
    )
    second = store.record(
        observation(
            "ERROR",
            age=9,
            url="https://www.amazon.it/gp/product/B012345678?tag=two",
            claim="Legacy alternate key",
        )
    )
    with sqlite3.connect(path) as db:
        latest = db.execute(
            "SELECT latest_id FROM claims WHERE claim_id=?", (second["claim_id"],)
        ).fetchone()[0]
        data = json.loads(
            db.execute(
                "SELECT result_json FROM observations WHERE id=?", (latest,)
            ).fetchone()[0]
        )
        data["claim_text"] = first["result"]["claim_text"]
        db.execute(
            "UPDATE observations SET result_json=? WHERE id=?",
            (json.dumps(data), latest),
        )
        db.execute("PRAGMA user_version=0")
    migrated = VerificationStore(path).recall(url="https://amazon.it/dp/B012345678")
    assert migrated["total"] == 1
    assert migrated["claims"][0]["history_count"] == 2
    assert migrated["claims"][0]["result"]["outcome"] == "ERROR"
    assert migrated["claims"][0]["do_not_reuse_prior_assertion"] is True
