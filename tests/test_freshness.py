"""Contract tests for policy resolution and deterministic freshness evaluation."""

from datetime import UTC, datetime, timedelta, timezone

import pytest

from factttl.freshness import (
    FreshnessResult,
    ResolvedPolicy,
    ReviewPolicy,
    evaluate_freshness,
    resolve_policy,
)


def status_of(result: object) -> str:
    """Support either string statuses or a string-valued enum."""
    status = getattr(result, "status")
    return str(getattr(status, "value", status)).upper()


def evaluate(
    *,
    last_checked_at: datetime | None,
    evaluation_time: datetime,
    temporal_class: str | None = "TIME_SENSITIVE",
    per_claim: ReviewPolicy | None = None,
    category: ReviewPolicy | None = None,
) -> FreshnessResult:
    policy = resolve_policy(
        temporal_class=temporal_class,
        per_claim=per_claim,
        category=category,
    )
    return evaluate_freshness(
        policy=policy,
        last_checked_at=last_checked_at,
        evaluation_time=evaluation_time,
    )


def test_per_claim_ttl_overrides_category_disable() -> None:
    checked = datetime(2026, 1, 1, tzinfo=UTC)
    result = evaluate(
        last_checked_at=checked,
        evaluation_time=checked + timedelta(minutes=30),
        per_claim=ReviewPolicy(ttl=timedelta(hours=1)),
        category=ReviewPolicy(review_disabled=True),
    )

    assert status_of(result) == "FRESH"
    assert result.review_due_at == checked + timedelta(hours=1)


def test_per_claim_disable_overrides_category_ttl() -> None:
    result = evaluate(
        last_checked_at=None,
        evaluation_time=datetime(2026, 1, 1, tzinfo=UTC),
        per_claim=ReviewPolicy(review_disabled=True),
        category=ReviewPolicy(ttl=timedelta(hours=1)),
    )

    assert status_of(result) == "NOT_REQUIRED"
    assert result.review_due_at is None


def test_not_required_does_not_consult_an_unneeded_timestamp() -> None:
    result = evaluate(
        last_checked_at=datetime(2026, 1, 1),
        evaluation_time=datetime(2026, 1, 1, tzinfo=UTC),
        per_claim=ReviewPolicy(review_disabled=True),
    )

    assert status_of(result) == "NOT_REQUIRED"
    assert result.last_checked_at is None


def test_category_ttl_applies_to_stable_class() -> None:
    checked = datetime(2026, 1, 1, tzinfo=UTC)
    result = evaluate(
        last_checked_at=checked,
        evaluation_time=checked + timedelta(hours=1),
        temporal_class="STABLE",
        category=ReviewPolicy(ttl=timedelta(hours=2)),
    )

    assert status_of(result) == "FRESH"
    assert result.review_due_at == checked + timedelta(hours=2)


def test_stable_fallback_is_not_required_only_without_scoped_policy() -> None:
    result = evaluate(
        last_checked_at=None,
        evaluation_time=datetime(2026, 1, 1, tzinfo=UTC),
        temporal_class="STABLE",
    )

    assert status_of(result) == "NOT_REQUIRED"


@pytest.mark.parametrize(
    "temporal_class", ["TIME_SENSITIVE", "HIGHLY_VOLATILE", "UNKNOWN", None]
)
def test_unresolved_non_stable_policy_is_unknown(temporal_class: str | None) -> None:
    result = evaluate(
        last_checked_at=None,
        evaluation_time=datetime(2026, 1, 1, tzinfo=UTC),
        temporal_class=temporal_class,
    )

    assert status_of(result) == "UNKNOWN"
    assert result.review_due_at is None
    assert result.reason


@pytest.mark.parametrize("temporal_class", ["STABLE", "UNKNOWN"])
def test_per_claim_ttl_applies_to_stable_or_unknown_class(temporal_class: str) -> None:
    checked = datetime(2026, 1, 1, tzinfo=UTC)
    result = evaluate(
        last_checked_at=checked,
        evaluation_time=checked + timedelta(minutes=30),
        temporal_class=temporal_class,
        per_claim=ReviewPolicy(ttl=timedelta(hours=1)),
    )

    assert status_of(result) == "FRESH"
    assert result.review_due_at == checked + timedelta(hours=1)


@pytest.mark.parametrize(
    ("evaluation_delta", "expected_status"),
    [
        (timedelta(days=1) - timedelta(microseconds=1), "FRESH"),
        (timedelta(days=1), "STALE"),
        (timedelta(days=1, microseconds=1), "STALE"),
    ],
)
def test_deadline_boundary(evaluation_delta: timedelta, expected_status: str) -> None:
    checked = datetime(2026, 1, 1, tzinfo=UTC)
    result = evaluate(
        last_checked_at=checked,
        evaluation_time=checked + evaluation_delta,
        per_claim=ReviewPolicy(ttl=timedelta(days=1)),
    )

    assert status_of(result) == expected_status
    assert result.review_due_at == checked + timedelta(days=1)


def test_zero_ttl_is_stale_at_check_time() -> None:
    checked = datetime(2026, 1, 1, tzinfo=UTC)
    result = evaluate(
        last_checked_at=checked,
        evaluation_time=checked,
        per_claim=ReviewPolicy(ttl=timedelta(0)),
    )

    assert status_of(result) == "STALE"
    assert result.review_due_at == checked


def test_evaluation_is_deterministic_and_uses_supplied_time() -> None:
    checked = datetime(2026, 1, 1, tzinfo=UTC)
    policy = resolve_policy(
        temporal_class="TIME_SENSITIVE",
        per_claim=ReviewPolicy(ttl=timedelta(hours=2)),
    )
    early = checked + timedelta(hours=1)
    late = checked + timedelta(hours=3)

    first = evaluate_freshness(
        policy=policy, last_checked_at=checked, evaluation_time=early
    )
    repeated = evaluate_freshness(
        policy=policy, last_checked_at=checked, evaluation_time=early
    )
    later = evaluate_freshness(
        policy=policy, last_checked_at=checked, evaluation_time=late
    )

    assert status_of(first) == status_of(repeated) == "FRESH"
    assert first.reason == repeated.reason
    assert first.review_due_at == repeated.review_due_at
    assert status_of(later) == "STALE"


def test_aware_timestamps_with_different_offsets_compare_as_same_instant() -> None:
    checked = datetime(2026, 4, 1, 12, tzinfo=timezone(timedelta(hours=2)))
    evaluation = datetime(2026, 4, 1, 11, tzinfo=timezone(timedelta(hours=1)))
    result = evaluate(
        last_checked_at=checked,
        evaluation_time=evaluation,
        per_claim=ReviewPolicy(ttl=timedelta(0)),
    )

    assert status_of(result) == "STALE"
    assert result.review_due_at == checked


def test_missing_check_for_required_policy_is_unverified() -> None:
    result = evaluate(
        last_checked_at=None,
        evaluation_time=datetime(2026, 1, 1, tzinfo=UTC),
        per_claim=ReviewPolicy(ttl=timedelta(days=1)),
    )

    assert status_of(result) == "UNVERIFIED"
    assert result.review_due_at is None


def test_future_check_time_returns_unknown() -> None:
    checked = datetime(2026, 1, 2, tzinfo=UTC)
    result = evaluate(
        last_checked_at=checked,
        evaluation_time=checked - timedelta(seconds=1),
        per_claim=ReviewPolicy(ttl=timedelta(days=1)),
    )

    assert status_of(result) == "UNKNOWN"
    assert result.reason


@pytest.mark.parametrize(
    ("last_checked_at", "evaluation_time"),
    [
        (datetime(2026, 1, 1), datetime(2026, 1, 2, tzinfo=UTC)),
        (datetime(2026, 1, 1, tzinfo=UTC), datetime(2026, 1, 2)),
    ],
)
def test_naive_timestamps_raise_validation_error(
    last_checked_at: datetime, evaluation_time: datetime
) -> None:
    with pytest.raises(ValueError):
        evaluate(
            last_checked_at=last_checked_at,
            evaluation_time=evaluation_time,
            per_claim=ReviewPolicy(ttl=timedelta(days=1)),
        )


def test_negative_ttl_raises_validation_error() -> None:
    with pytest.raises(ValueError):
        ReviewPolicy(ttl=timedelta(seconds=-1))


def test_ttl_and_disable_are_mutually_exclusive() -> None:
    with pytest.raises(ValueError):
        ReviewPolicy(ttl=timedelta(days=1), review_disabled=True)


def test_directly_constructed_resolved_policy_is_validated() -> None:
    with pytest.raises(ValueError):
        ResolvedPolicy(
            ttl=timedelta(days=-1),
            review_disabled=False,
            is_resolved=True,
            reason="invalid negative duration",
        )

    with pytest.raises(ValueError):
        ResolvedPolicy(
            ttl=None,
            review_disabled=False,
            is_resolved=True,
            reason="no effective setting",
        )


def test_due_time_overflow_has_clear_validation_error() -> None:
    checked = datetime.max.replace(tzinfo=UTC)
    policy = resolve_policy(
        temporal_class="TIME_SENSITIVE",
        per_claim=ReviewPolicy(ttl=timedelta(days=1)),
    )

    with pytest.raises(ValueError, match="supported datetime range"):
        evaluate_freshness(
            policy=policy,
            last_checked_at=checked,
            evaluation_time=checked,
        )


def test_timezone_offset_outside_utc_range_has_clear_validation_error() -> None:
    policy = resolve_policy(
        temporal_class="TIME_SENSITIVE",
        per_claim=ReviewPolicy(ttl=timedelta(days=1)),
    )
    checked = datetime(1, 1, 1, tzinfo=timezone(timedelta(hours=1)))

    with pytest.raises(ValueError, match="supported UTC datetime range"):
        evaluate_freshness(
            policy=policy,
            last_checked_at=checked,
            evaluation_time=datetime(1, 1, 2, tzinfo=UTC),
        )


def test_evaluator_works_when_network_connections_are_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The core decision must not require an online provider or service."""
    import socket

    def reject_network(*args: object, **kwargs: object) -> None:
        raise AssertionError("freshness evaluation must not access the network")

    monkeypatch.setattr(socket, "create_connection", reject_network)
    checked = datetime(2026, 1, 1, tzinfo=UTC)
    result = evaluate(
        last_checked_at=checked,
        evaluation_time=checked,
        per_claim=ReviewPolicy(ttl=timedelta(days=1)),
    )

    assert status_of(result) == "FRESH"
