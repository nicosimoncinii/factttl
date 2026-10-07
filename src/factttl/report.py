"""Deterministic reports for caller-supplied claim candidates."""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from types import MappingProxyType

from factttl.config import PolicyConfig
from factttl.freshness import (
    FreshnessResult,
    FreshnessStatus,
    ResolvedPolicy,
    ReviewPolicy,
    TemporalClass,
    evaluate_freshness,
    resolve_policy,
)

_CATEGORY_NAME = re.compile(r"^[a-z][a-z0-9_]*$")


@dataclass(frozen=True, slots=True)
class ClaimCandidate:
    """A claim supplied by the caller; this model does not verify its truth."""

    text: str
    id: str | None = None
    category: str | None = None
    temporal_class: TemporalClass | str | None = None
    last_checked_at: datetime | None = None
    policy: ReviewPolicy | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.text, str) or not self.text.strip():
            raise ValueError("claim text must be a non-empty string")
        if self.id is not None and (
            not isinstance(self.id, str) or not self.id.strip()
        ):
            raise ValueError("claim id must be a non-empty string or None")
        if self.category is not None and not isinstance(self.category, str):
            raise TypeError("category must be a string or None")
        if (
            self.category is not None
            and _CATEGORY_NAME.fullmatch(self.category) is None
        ):
            raise ValueError(
                "category must start with a lowercase letter and use only "
                "lowercase letters, digits, or underscores"
            )
        if self.temporal_class is not None:
            try:
                normalized_class = TemporalClass(self.temporal_class)
            except (TypeError, ValueError):
                normalized_class = TemporalClass.UNKNOWN
            object.__setattr__(self, "temporal_class", normalized_class)
        if self.policy is not None and not isinstance(self.policy, ReviewPolicy):
            raise TypeError("policy must be a ReviewPolicy or None")


@dataclass(frozen=True, slots=True)
class ClaimReportRow:
    """One candidate's status, resolved policy provenance, and optional text."""

    id: str
    text: str | None
    category: str | None
    temporal_class: TemporalClass | str | None
    policy: ResolvedPolicy
    result: FreshnessResult

    @property
    def status(self) -> FreshnessStatus:
        """Convenience access to the evaluated freshness status."""
        return self.result.status


@dataclass(frozen=True, slots=True)
class FreshnessReport:
    """Ordered report and counts for every defined freshness status."""

    evaluation_time: datetime
    rows: tuple[ClaimReportRow, ...]
    counts: Mapping[FreshnessStatus, int]

    def __post_init__(self) -> None:
        object.__setattr__(self, "counts", MappingProxyType(dict(self.counts)))

    @property
    def total(self) -> int:
        """Number of claim candidates in the report."""
        return len(self.rows)


def build_report(
    claims: Iterable[ClaimCandidate],
    *,
    evaluation_time: datetime,
    policy_config: PolicyConfig | None = None,
    include_claim_text: bool = True,
) -> FreshnessReport:
    """Evaluate caller-supplied candidates in order, without I/O or clock access.

    Missing IDs are assigned ``claim-N`` using their one-based input position.
    Explicit IDs must be unique. Text is included by default; set
    ``include_claim_text=False`` when report contents may leave a trusted boundary.
    """
    if not isinstance(include_claim_text, bool):
        raise TypeError("include_claim_text must be a bool")
    if not isinstance(evaluation_time, datetime):
        raise TypeError("evaluation_time must be a datetime")
    if evaluation_time.tzinfo is None or evaluation_time.utcoffset() is None:
        raise ValueError("evaluation_time must be timezone-aware")
    try:
        normalized_evaluation_time = evaluation_time.astimezone(UTC)
    except OverflowError as error:
        raise ValueError(
            "evaluation_time is outside the supported UTC datetime range"
        ) from error
    if policy_config is not None and not isinstance(policy_config, PolicyConfig):
        raise TypeError("policy_config must be a PolicyConfig or None")

    candidates = tuple(claims)
    if any(not isinstance(candidate, ClaimCandidate) for candidate in candidates):
        raise TypeError("claims must contain only ClaimCandidate instances")

    identifiers: list[str] = []
    seen: set[str] = set()
    for position, candidate in enumerate(candidates, start=1):
        identifier = candidate.id if candidate.id is not None else f"claim-{position}"
        if identifier in seen:
            raise ValueError(f"duplicate claim id: {identifier!r}")
        seen.add(identifier)
        identifiers.append(identifier)

    rows: list[ClaimReportRow] = []
    for candidate, identifier in zip(candidates, identifiers, strict=True):
        category_policy = (
            policy_config.category_policy(candidate.category)
            if policy_config is not None
            else None
        )
        resolved = resolve_policy(
            temporal_class=candidate.temporal_class,
            per_claim=candidate.policy,
            category=category_policy,
        )
        result = evaluate_freshness(
            policy=resolved,
            last_checked_at=candidate.last_checked_at,
            evaluation_time=evaluation_time,
        )
        rows.append(
            ClaimReportRow(
                id=identifier,
                text=candidate.text if include_claim_text else None,
                category=candidate.category,
                temporal_class=candidate.temporal_class,
                policy=resolved,
                result=result,
            )
        )

    counts = Counter(row.status for row in rows)
    complete_counts = {status: counts[status] for status in FreshnessStatus}
    return FreshnessReport(
        evaluation_time=normalized_evaluation_time,
        rows=tuple(rows),
        counts=complete_counts,
    )
