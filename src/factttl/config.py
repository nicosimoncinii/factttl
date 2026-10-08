"""Load and semantically validate local FactTTL policy TOML."""

from __future__ import annotations

import re
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from types import MappingProxyType
from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictInt,
    ValidationError,
    field_validator,
    model_validator,
)

from factttl.freshness import ReviewPolicy

_DURATION = re.compile(r"^(0|[1-9][0-9]*)(s|m|h|d|w)$")
_CATEGORY = re.compile(r"^[a-z][a-z0-9_]*$")
_UNIT_SECONDS = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}
CategoryName = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]*$")]


class PolicyConfigError(ValueError):
    """Invalid or unreadable FactTTL policy configuration."""


class _CategorySettings(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    ttl: timedelta | None = None
    review_disabled: StrictBool | None = None

    @field_validator("ttl", mode="before")
    @classmethod
    def parse_duration(cls, value: object) -> object:
        if value is None or isinstance(value, timedelta):
            return value
        if not isinstance(value, str):
            raise ValueError("must be a duration string such as '24h' or '7d'")
        match = _DURATION.fullmatch(value)
        if match is None:
            raise ValueError(
                "duration must use a non-negative integer and unit s, m, h, d, or w "
                "(examples: '0s', '24h', '7d')"
            )
        amount, unit = match.groups()
        try:
            return timedelta(seconds=int(amount) * _UNIT_SECONDS[unit])
        except OverflowError as error:
            raise ValueError("is too large to represent") from error

    @model_validator(mode="after")
    def check_policy(self) -> _CategorySettings:
        if self.ttl is not None and self.review_disabled is not None:
            raise ValueError("choose either ttl or review_disabled, not both")
        if self.ttl is None and self.review_disabled is not True:
            raise ValueError("set ttl or set review_disabled = true")
        return self


class _ConfigDocument(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    schema_version: StrictInt
    categories: dict[CategoryName, _CategorySettings]

    @field_validator("schema_version")
    @classmethod
    def supported_version(cls, value: int) -> int:
        if value != 1:
            raise ValueError("only schema_version = 1 is supported")
        return value


@dataclass(frozen=True, slots=True)
class PolicyConfig:
    """Validated category policies loaded from a local file or TOML text."""

    categories: Mapping[str, ReviewPolicy]
    schema_version: int = 1

    def __post_init__(self) -> None:
        if type(self.schema_version) is not int or self.schema_version != 1:
            raise ValueError("schema_version must be the integer 1")
        if not isinstance(self.categories, Mapping):
            raise TypeError(
                "categories must be a mapping of category names to policies"
            )
        for category, policy in self.categories.items():
            if not isinstance(category, str) or _CATEGORY.fullmatch(category) is None:
                raise ValueError(f"invalid category name: {category!r}")
            if not isinstance(policy, ReviewPolicy):
                raise TypeError(f"categories[{category!r}] must be a ReviewPolicy")
        object.__setattr__(self, "categories", MappingProxyType(dict(self.categories)))

    def category_policy(self, category: str | None) -> ReviewPolicy | None:
        """Return the configured policy for a category, if one exists."""
        if category is None:
            return None
        if not isinstance(category, str) or _CATEGORY.fullmatch(category) is None:
            raise ValueError(f"invalid category name: {category!r}")
        return self.categories.get(category)


def parse_policy_toml(source: str) -> PolicyConfig:
    """Parse and validate TOML policy text; no files, network, or clock are accessed."""
    if not isinstance(source, str):
        raise TypeError("source must be a string")
    try:
        raw = tomllib.loads(source)
    except tomllib.TOMLDecodeError as error:
        raise PolicyConfigError(f"Invalid TOML: {error}") from error
    try:
        document = _ConfigDocument.model_validate(raw)
    except ValidationError as error:
        details = "; ".join(
            f"{'.'.join(str(part) for part in item['loc'])}: {item['msg']}"
            for item in error.errors()
        )
        raise PolicyConfigError(f"Invalid policy configuration: {details}") from error

    policies: dict[str, ReviewPolicy] = {}
    for category, settings in document.categories.items():
        try:
            policies[category] = ReviewPolicy(
                ttl=settings.ttl,
                review_disabled=settings.review_disabled is True,
            )
        except (TypeError, ValueError) as error:
            raise PolicyConfigError(
                f"Invalid categories.{category} policy: {error}"
            ) from error
    return PolicyConfig(categories=policies, schema_version=document.schema_version)


def load_policy(path: str | Path) -> PolicyConfig:
    """Read a UTF-8 TOML policy file and return validated category policies."""
    policy_path = Path(path)
    try:
        source = policy_path.read_text(encoding="utf-8")
    except OSError as error:
        raise PolicyConfigError(
            f"Cannot read policy file '{policy_path}': {error}"
        ) from error
    except UnicodeError as error:
        raise PolicyConfigError(
            f"Policy file '{policy_path}' must be UTF-8."
        ) from error
    try:
        return parse_policy_toml(source)
    except PolicyConfigError as error:
        raise PolicyConfigError(f"Policy file '{policy_path}': {error}") from error
