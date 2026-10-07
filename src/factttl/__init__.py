"""Public API for FactTTL's deterministic freshness tooling.

Importing the freshness package does not import configuration/report extras;
those Pydantic-backed boundaries load only when their public symbols are used.
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

from factttl.freshness import (
    FreshnessResult,
    FreshnessStatus,
    ResolvedPolicy,
    ReviewPolicy,
    TemporalClass,
    evaluate_freshness,
    resolve_policy,
)

if TYPE_CHECKING:
    from factttl.config import (
        PolicyConfig,
        PolicyConfigError,
        load_policy,
        parse_policy_toml,
    )
    from factttl.report import (
        ClaimCandidate,
        ClaimReportRow,
        FreshnessReport,
        build_report,
    )

_CONFIG_EXPORTS = frozenset(
    {"PolicyConfig", "PolicyConfigError", "load_policy", "parse_policy_toml"}
)
_REPORT_EXPORTS = frozenset(
    {"ClaimCandidate", "ClaimReportRow", "FreshnessReport", "build_report"}
)

__all__ = [
    "ClaimCandidate",
    "ClaimReportRow",
    "FreshnessReport",
    "FreshnessResult",
    "FreshnessStatus",
    "PolicyConfig",
    "PolicyConfigError",
    "ResolvedPolicy",
    "ReviewPolicy",
    "TemporalClass",
    "build_report",
    "evaluate_freshness",
    "load_policy",
    "parse_policy_toml",
    "resolve_policy",
]


def __getattr__(name: str) -> Any:
    """Load optional API boundaries only when their symbols are requested."""
    if name in _CONFIG_EXPORTS:
        module = import_module(".config", __name__)
    elif name in _REPORT_EXPORTS:
        module = import_module(".report", __name__)
    else:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    return getattr(module, name)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
