"""Evidence observations, distinct from a claim's age or universal truth."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from urllib.parse import urlsplit

OUTCOMES = frozenset({"SUPPORTED", "CONTRADICTED", "INCONCLUSIVE", "ERROR"})


def parse_timestamp(value: str) -> datetime:
    """Parse an explicitly timezone-aware observation time."""
    if not isinstance(value, str) or len(value) > 64:
        raise ValueError("timestamps must be ISO strings of at most 64 characters")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("timestamps must be valid ISO 8601 dates") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("timestamps require an explicit timezone")
    return parsed.astimezone(UTC)


def validate_url(value: str) -> str:
    """Validate the stored source identifier; this does not perform any request."""
    if not isinstance(value, str) or not value or len(value) > 8192:
        raise ValueError("url must be a non-empty string of at most 8192 characters")
    if any(ord(char) < 32 for char in value):
        raise ValueError("url must not contain control characters")
    try:
        parsed = urlsplit(value)
        _ = parsed.port
    except ValueError as exc:
        raise ValueError("url is invalid") from exc
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        raise ValueError("url must be an absolute HTTP or HTTPS URL")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("url must not contain credentials")
    return value


def _text(value: object, field: str, maximum: int, *, optional: bool = False) -> None:
    if optional and value is None:
        return
    if not isinstance(value, str) or len(value) > maximum:
        raise ValueError(f"{field} must be a string of at most {maximum} characters")
    if not optional and not value.strip():
        raise ValueError(f"{field} must not be empty")


@dataclass(frozen=True, slots=True)
class VerificationResult:
    """What evidence supported a specific assertion at a specific instant."""

    url: str
    kind: str
    outcome: str
    observed_at: str
    rationale: str
    evidence: list[dict[str, object]]
    observed_value: str | None = None
    published_at: str | None = None
    expected_value: str | None = None
    claim_text: str | None = None

    def __post_init__(self) -> None:
        validate_url(self.url)
        _text(self.kind, "kind", 128)
        _text(self.rationale, "rationale", 8000)
        if self.outcome not in OUTCOMES:
            raise ValueError(
                "outcome must be SUPPORTED, CONTRADICTED, INCONCLUSIVE or ERROR"
            )
        object.__setattr__(
            self, "observed_at", parse_timestamp(self.observed_at).isoformat()
        )
        if self.published_at is not None:
            object.__setattr__(
                self, "published_at", parse_timestamp(self.published_at).isoformat()
            )
        for field in ("observed_value", "expected_value", "claim_text"):
            _text(getattr(self, field), field, 4000, optional=True)
        if (
            not isinstance(self.evidence, list)
            or len(self.evidence) > 50
            or any(not isinstance(item, dict) for item in self.evidence)
        ):
            raise ValueError("evidence must be a list of at most 50 dictionaries")
        try:
            encoded = json.dumps(self.evidence, allow_nan=False, ensure_ascii=False)
        except (TypeError, ValueError) as exc:
            raise ValueError("evidence must contain JSON-compatible values") from exc
        if len(encoded.encode("utf-8")) > 262144:
            raise ValueError("evidence must be at most 256 KiB")
        if self.outcome in {"SUPPORTED", "CONTRADICTED"} and not any(self.evidence):
            raise ValueError("a definitive observation requires explicit evidence")

    def as_dict(self) -> dict[str, object]:
        """Return a detached, JSON-compatible observation."""
        return asdict(self)
