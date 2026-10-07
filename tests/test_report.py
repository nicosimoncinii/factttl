from datetime import UTC, datetime, timedelta

import pytest

from factttl.config import parse_policy_toml
from factttl.freshness import FreshnessStatus, ReviewPolicy, TemporalClass
from factttl.report import ClaimCandidate, build_report

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def test_report_evaluates_in_input_order_and_counts_every_status() -> None:
    policy = parse_policy_toml(
        'schema_version = 1\n[categories.news]\nttl = "1d"\n'
        "[categories.archive]\nreview_disabled = true\n"
    )
    claims = [
        ClaimCandidate(
            id="old-news",
            text="Old headline",
            category="news",
            temporal_class=TemporalClass.TIME_SENSITIVE,
            last_checked_at=NOW - timedelta(days=1),
        ),
        ClaimCandidate(
            text="No policy",
            temporal_class=TemporalClass.TIME_SENSITIVE,
        ),
        ClaimCandidate(text="Archived", category="archive"),
        ClaimCandidate(
            id="fresh-news",
            text="Recent headline",
            category="news",
            temporal_class=TemporalClass.UNKNOWN,
            last_checked_at=NOW,
        ),
    ]

    report = build_report(claims, evaluation_time=NOW, policy_config=policy)

    assert [row.id for row in report.rows] == [
        "old-news",
        "claim-2",
        "claim-3",
        "fresh-news",
    ]
    assert [row.status for row in report.rows] == [
        FreshnessStatus.STALE,
        FreshnessStatus.UNKNOWN,
        FreshnessStatus.NOT_REQUIRED,
        FreshnessStatus.FRESH,
    ]
    assert report.total == 4
    assert dict(report.counts) == {
        FreshnessStatus.FRESH: 1,
        FreshnessStatus.STALE: 1,
        FreshnessStatus.UNVERIFIED: 0,
        FreshnessStatus.NOT_REQUIRED: 1,
        FreshnessStatus.UNKNOWN: 1,
    }
    assert report.rows[0].policy.reason == "TTL was resolved from category policy."


def test_per_claim_policy_overrides_category_policy_and_keeps_provenance() -> None:
    config = parse_policy_toml(
        "schema_version = 1\n[categories.archive]\nreview_disabled = true\n"
    )
    report = build_report(
        [
            ClaimCandidate(
                text="Override",
                category="archive",
                temporal_class=TemporalClass.STABLE,
                policy=ReviewPolicy(ttl=timedelta(hours=1)),
            )
        ],
        evaluation_time=NOW,
        policy_config=config,
    )
    assert report.rows[0].status is FreshnessStatus.UNVERIFIED
    assert report.rows[0].policy.reason == "TTL was resolved from per-claim policy."


def test_report_can_omit_text_for_privacy() -> None:
    report = build_report(
        [ClaimCandidate(id="private", text="Sensitive claim")],
        evaluation_time=NOW,
        include_claim_text=False,
    )
    assert report.rows[0].text is None
    assert report.rows[0].status is FreshnessStatus.UNKNOWN


def test_invalid_temporal_class_is_normalized_to_unknown() -> None:
    report = build_report(
        [ClaimCandidate(text="Claim", temporal_class="STABLEE")],
        evaluation_time=NOW,
    )

    assert report.rows[0].temporal_class is TemporalClass.UNKNOWN
    assert report.rows[0].status is FreshnessStatus.UNKNOWN


def test_invalid_category_key_is_rejected() -> None:
    with pytest.raises(ValueError, match="category must start"):
        ClaimCandidate(text="Claim", category="Bad-Key")


def test_duplicate_ids_are_rejected_including_fallback_collision() -> None:
    with pytest.raises(ValueError, match="duplicate claim id"):
        build_report(
            [
                ClaimCandidate(id="claim-2", text="Explicit"),
                ClaimCandidate(text="Generated claim-2"),
            ],
            evaluation_time=NOW,
        )


def test_non_claims_and_naive_evaluation_time_are_rejected() -> None:
    with pytest.raises(TypeError, match="ClaimCandidate"):
        build_report([object()], evaluation_time=NOW)  # type: ignore[list-item]
    with pytest.raises(ValueError, match="timezone-aware"):
        build_report([], evaluation_time=datetime(2026, 1, 1))


def test_empty_report_has_zero_for_each_status_and_utc_time() -> None:
    report = build_report([], evaluation_time=NOW)
    assert report.total == 0
    assert set(report.counts) == set(FreshnessStatus)
    assert all(value == 0 for value in report.counts.values())
    assert report.evaluation_time == NOW
