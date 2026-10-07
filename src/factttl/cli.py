"""Command-line interface for deterministic, caller-supplied freshness scans."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictInt,
    StrictStr,
    ValidationError,
    field_validator,
    model_validator,
)

from factttl.config import PolicyConfigError, load_policy
from factttl.freshness import FreshnessStatus, ReviewPolicy, TemporalClass
from factttl.report import ClaimCandidate, FreshnessReport, build_report

_MAX_INPUT_BYTES = 10 * 1024 * 1024


class _InputClaim(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    id: StrictStr | None = None
    text: StrictStr
    category: StrictStr | None = None
    temporal_class: (
        Literal["STABLE", "TIME_SENSITIVE", "HIGHLY_VOLATILE", "UNKNOWN"] | None
    ) = None
    last_checked_at: datetime | None = None
    ttl_seconds: Annotated[StrictInt, Field(ge=0)] | None = None
    review_disabled: StrictBool | None = None

    @field_validator("text")
    @classmethod
    def non_empty_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be empty")
        return value

    @field_validator("id")
    @classmethod
    def non_empty_id(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("must not be empty")
        return value

    @field_validator("last_checked_at", mode="before")
    @classmethod
    def parse_checked_at(cls, value: object) -> object:
        return _parse_datetime(value, "last_checked_at") if value is not None else None

    @model_validator(mode="after")
    def valid_override(self) -> _InputClaim:
        if self.ttl_seconds is not None and self.review_disabled is True:
            raise ValueError("ttl_seconds and review_disabled are mutually exclusive")
        return self


class _InputDocument(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    schema_version: StrictInt
    evaluation_time: datetime
    claims: list[_InputClaim]

    @field_validator("schema_version")
    @classmethod
    def supported_version(cls, value: int) -> int:
        if value != 1:
            raise ValueError("only schema_version = 1 is supported")
        return value

    @field_validator("evaluation_time", mode="before")
    @classmethod
    def parse_evaluation_time(cls, value: object) -> object:
        return _parse_datetime(value, "evaluation_time")


def _parse_datetime(value: object, field: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be an ISO 8601 timestamp string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError(f"{field} must be a valid ISO 8601 timestamp") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} must include a timezone, such as Z or +02:00")
    return parsed


def _utc_string(value: datetime | None) -> str | None:
    if value is None:
        return None
    return (
        value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")
    )


def _report_document(report: FreshnessReport) -> dict[str, object]:
    rows: list[dict[str, object]] = []
    for row in report.rows:
        result = row.result
        rows.append(
            {
                "id": row.id,
                "text": row.text,
                "category": row.category,
                "temporal_class": (
                    row.temporal_class.value
                    if isinstance(row.temporal_class, TemporalClass)
                    else row.temporal_class
                ),
                "status": row.status.value,
                "policy": {
                    "ttl_seconds": (
                        row.policy.ttl.total_seconds()
                        if row.policy.ttl is not None
                        else None
                    ),
                    "review_disabled": row.policy.review_disabled,
                    "is_resolved": row.policy.is_resolved,
                    "reason": row.policy.reason,
                },
                "result": {
                    "evaluation_time": _utc_string(result.evaluation_time),
                    "last_checked_at": _utc_string(result.last_checked_at),
                    "review_due_at": _utc_string(result.review_due_at),
                    "ttl_seconds": (
                        result.resolved_ttl.total_seconds()
                        if result.resolved_ttl is not None
                        else None
                    ),
                    "reason": result.reason,
                },
            }
        )
    return {
        "schema_version": 1,
        "evaluation_time": _utc_string(report.evaluation_time),
        "counts": {status.value: report.counts[status] for status in FreshnessStatus},
        "total": report.total,
        "rows": rows,
    }


def _render_text(report: FreshnessReport) -> str:
    lines = [
        f"FactTTL scan at {_utc_string(report.evaluation_time)}",
        "Counts: "
        + ", ".join(
            f"{status.value}={report.counts[status]}" for status in FreshnessStatus
        )
        + f" (total={report.total})",
    ]
    for row in report.rows:
        claim_text = json.dumps(row.text, ensure_ascii=False)
        lines.append(f"{row.status.value}  {row.id}  {claim_text}")
        lines.append(f"  Policy: {row.policy.reason}")
        lines.append(f"  Result: {row.result.reason}")
    return "\n".join(lines) + "\n"


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    """Reject duplicate JSON keys instead of silently taking the last value."""
    document: dict[str, object] = {}
    for key, value in pairs:
        if key in document:
            raise ValueError(f"duplicate JSON key: {key!r}")
        document[key] = value
    return document


def _read_input(path: str) -> str:
    try:
        if path == "-":
            if hasattr(sys.stdin, "buffer"):
                data = sys.stdin.buffer.read(_MAX_INPUT_BYTES + 1)
                if len(data) > _MAX_INPUT_BYTES:
                    raise ValueError("Input exceeds the 10 MiB size limit.")
                return data.decode("utf-8")
            text = sys.stdin.read(_MAX_INPUT_BYTES + 1)
            if len(text.encode("utf-8")) > _MAX_INPUT_BYTES:
                raise ValueError("Input exceeds the 10 MiB size limit.")
            return text
        with Path(path).open("rb") as input_file:
            data = input_file.read(_MAX_INPUT_BYTES + 1)
        if len(data) > _MAX_INPUT_BYTES:
            raise ValueError("Input exceeds the 10 MiB size limit.")
        return data.decode("utf-8")
    except OSError as error:
        raise ValueError(f"Cannot read input '{path}': {error}") from error
    except UnicodeError as error:
        raise ValueError(f"Input '{path}' must be UTF-8.") from error


def _evaluate(document: _InputDocument, policy_path: str | None) -> FreshnessReport:
    policy_config = load_policy(policy_path) if policy_path is not None else None
    claims = []
    for claim in document.claims:
        override = None
        if claim.ttl_seconds is not None or claim.review_disabled is True:
            try:
                ttl = (
                    timedelta(seconds=claim.ttl_seconds)
                    if claim.ttl_seconds is not None
                    else None
                )
            except OverflowError as error:
                raise ValueError(
                    f"claim {claim.id!r} ttl_seconds is too large to represent"
                ) from error
            override = ReviewPolicy(
                ttl=ttl,
                review_disabled=claim.review_disabled is True,
            )
        claims.append(
            ClaimCandidate(
                id=claim.id,
                text=claim.text,
                category=claim.category,
                temporal_class=claim.temporal_class,
                last_checked_at=claim.last_checked_at,
                policy=override,
            )
        )
    return build_report(
        claims,
        evaluation_time=document.evaluation_time,
        policy_config=policy_config,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="factttl",
        description=(
            "Evaluate caller-supplied claims; no claims are extracted or verified."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    scan = subparsers.add_parser("scan", help="evaluate a UTF-8 JSON claims document")
    scan.add_argument(
        "file",
        nargs="?",
        default="-",
        help="input JSON file, or - for standard input (default: -)",
    )
    scan.add_argument(
        "--policy", metavar="PATH", help="optional local TOML policy file"
    )
    scan.add_argument(
        "--format", choices=("text", "json"), default="text", help="output format"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the FactTTL CLI; return zero for valid evaluations of any status."""
    args = _parser().parse_args(argv)
    try:
        source = _read_input(args.file)
        try:
            raw = json.loads(source, object_pairs_hook=_unique_object)
        except json.JSONDecodeError as error:
            raise ValueError(
                f"Invalid JSON at line {error.lineno}, column {error.colno}: "
                f"{error.msg}"
            ) from error
        try:
            document = _InputDocument.model_validate(raw)
        except ValidationError as error:
            details = "; ".join(
                f"{'.'.join(str(part) for part in item['loc'])}: {item['msg']}"
                for item in error.errors()
            )
            raise ValueError(f"Invalid input document: {details}") from error
        report = _evaluate(document, args.policy)
    except (PolicyConfigError, ValueError, TypeError) as error:
        print(f"factttl: error: {error}", file=sys.stderr)
        return 2

    if args.format == "json":
        print(json.dumps(_report_document(report), indent=2, ensure_ascii=False))
    else:
        print(_render_text(report), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
