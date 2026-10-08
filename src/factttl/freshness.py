"""Deterministic, local evaluation of a claim's review freshness."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum


class FreshnessStatus(StrEnum):
    """Possible outcomes of a freshness evaluation."""

    FRESH = "FRESH"
    STALE = "STALE"
    UNVERIFIED = "UNVERIFIED"
    NOT_REQUIRED = "NOT_REQUIRED"
    UNKNOWN = "UNKNOWN"


class TemporalClass(StrEnum):
    """Temporal classification used when no explicit TTL policy is set."""

    STABLE = "STABLE"
    TIME_SENSITIVE = "TIME_SENSITIVE"
    HIGHLY_VOLATILE = "HIGHLY_VOLATILE"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class ReviewPolicy:
    """Policy at one scope; neither field set means this scope is unspecified."""

    ttl: timedelta | None = None
    review_disabled: bool = False

    def __post_init__(self) -> None:
        if self.ttl is not None and not isinstance(self.ttl, timedelta):
            raise TypeError("ttl must be a datetime.timedelta or None")
        if self.ttl is not None and self.ttl < timedelta(0):
            raise ValueError("ttl must not be negative")
        if not isinstance(self.review_disabled, bool):
            raise TypeError("review_disabled must be a bool")
        if self.ttl is not None and self.review_disabled:
            raise ValueError("ttl and review_disabled are mutually exclusive")

    @property
    def is_specified(self) -> bool:
        """Whether this scope contains an explicit TTL or disable setting."""
        return self.ttl is not None or self.review_disabled


@dataclass(frozen=True, slots=True)
class ResolvedPolicy:
    """Effective policy after per-claim, category, and class precedence."""

    ttl: timedelta | None
    review_disabled: bool
    is_resolved: bool
    reason: str

    def __post_init__(self) -> None:
        if self.ttl is not None and not isinstance(self.ttl, timedelta):
            raise TypeError("ttl must be a datetime.timedelta or None")
        if self.ttl is not None and self.ttl < timedelta(0):
            raise ValueError("ttl must not be negative")
        if not isinstance(self.review_disabled, bool):
            raise TypeError("review_disabled must be a bool")
        if not isinstance(self.is_resolved, bool):
            raise TypeError("is_resolved must be a bool")
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise ValueError("reason must be a non-empty string")
        if self.ttl is not None and self.review_disabled:
            raise ValueError("ttl and review_disabled are mutually exclusive")
        if self.is_resolved != (self.ttl is not None or self.review_disabled):
            raise ValueError(
                "resolved policies must contain exactly one effective setting"
            )


@dataclass(frozen=True, slots=True)
class FreshnessResult:
    """Immutable freshness decision and the inputs/deadline used to make it."""

    status: FreshnessStatus
    reason: str
    evaluation_time: datetime
    resolved_ttl: timedelta | None
    last_checked_at: datetime | None
    review_due_at: datetime | None


def resolve_policy(
    *,
    temporal_class: TemporalClass | str | None,
    per_claim: ReviewPolicy | None = None,
    category: ReviewPolicy | None = None,
) -> ResolvedPolicy:
    """Resolve one effective policy, giving per-claim settings precedence."""
    for scope_name, scope in (("per_claim", per_claim), ("category", category)):
        if scope is not None and not isinstance(scope, ReviewPolicy):
            raise TypeError(f"{scope_name} must be a ReviewPolicy or None")
    resolved_class: TemporalClass | None
    if temporal_class is None:
        resolved_class = None
    else:
        try:
            resolved_class = TemporalClass(temporal_class)
        except (ValueError, TypeError):
            resolved_class = None

    for scope_name, scope in (("per-claim", per_claim), ("category", category)):
        if scope is not None and scope.is_specified:
            if scope.review_disabled:
                return ResolvedPolicy(
                    ttl=None,
                    review_disabled=True,
                    is_resolved=True,
                    reason=(
                        f"Routine review is explicitly disabled by {scope_name} policy."
                    ),
                )
            return ResolvedPolicy(
                ttl=scope.ttl,
                review_disabled=False,
                is_resolved=True,
                reason=f"TTL was resolved from {scope_name} policy.",
            )

    if resolved_class is TemporalClass.STABLE:
        return ResolvedPolicy(
            ttl=None,
            review_disabled=True,
            is_resolved=True,
            reason="STABLE class has no scoped TTL; routine review is not required.",
        )
    return ResolvedPolicy(
        ttl=None,
        review_disabled=False,
        is_resolved=False,
        reason="No scoped TTL or disable policy applies to this temporal class.",
    )


def _as_utc(value: datetime, *, field: str) -> datetime:
    """Validate an aware datetime and normalize it to UTC."""
    if not isinstance(value, datetime):
        raise TypeError(f"{field} must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field} must be timezone-aware")
    try:
        return value.astimezone(UTC)
    except OverflowError as error:
        raise ValueError(
            f"{field} is outside the supported UTC datetime range"
        ) from error


def evaluate_freshness(
    *,
    policy: ResolvedPolicy,
    last_checked_at: datetime | None,
    evaluation_time: datetime,
) -> FreshnessResult:
    """Evaluate a claim using an already-resolved policy, without I/O or clock access.

    The caller must pass ``last_checked_at`` only for a completed SUPPORTED or
    CONTRADICTED assessment. Category and per-claim policy precedence belongs in
    :func:`resolve_policy`, not in this timestamp evaluator.
    """
    if not isinstance(policy, ResolvedPolicy):
        raise TypeError("policy must be a ResolvedPolicy")
    evaluated_at = _as_utc(evaluation_time, field="evaluation_time")
    if policy.is_resolved and policy.review_disabled:
        return FreshnessResult(
            status=FreshnessStatus.NOT_REQUIRED,
            reason=policy.reason,
            evaluation_time=evaluated_at,
            resolved_ttl=None,
            last_checked_at=None,
            review_due_at=None,
        )
    checked_at = (
        _as_utc(last_checked_at, field="last_checked_at")
        if last_checked_at is not None
        else None
    )
    ttl = policy.ttl
    try:
        due_at = (
            checked_at + ttl if checked_at is not None and ttl is not None else None
        )
    except OverflowError as error:
        raise ValueError(
            "last_checked_at + ttl is outside the supported datetime range"
        ) from error

    def result(status: FreshnessStatus, reason: str) -> FreshnessResult:
        return FreshnessResult(
            status=status,
            reason=reason,
            evaluation_time=evaluated_at,
            resolved_ttl=ttl,
            last_checked_at=checked_at,
            review_due_at=due_at,
        )

    if not policy.is_resolved:
        return result(FreshnessStatus.UNKNOWN, policy.reason)
    if ttl is None:
        return result(FreshnessStatus.UNKNOWN, "Resolved review policy has no TTL.")
    if checked_at is not None and checked_at > evaluated_at:
        return result(
            FreshnessStatus.UNKNOWN,
            "last_checked_at is later than evaluation_time "
            "(future timestamp or clock skew).",
        )
    if checked_at is None:
        return result(
            FreshnessStatus.UNVERIFIED,
            "A review interval applies, but no qualifying check has been recorded.",
        )
    assert due_at is not None
    if evaluated_at >= due_at:
        return result(
            FreshnessStatus.STALE, "The review deadline has been reached or passed."
        )
    return result(FreshnessStatus.FRESH, "The review deadline has not been reached.")
