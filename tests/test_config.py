from datetime import timedelta
from pathlib import Path

import pytest

from factttl.config import (
    PolicyConfig,
    PolicyConfigError,
    load_policy,
    parse_policy_toml,
)
from factttl.freshness import ReviewPolicy


def test_loads_ttl_and_explicit_disable() -> None:
    config = parse_policy_toml(
        """
schema_version = 1

[categories.price]
ttl = "24h"

[categories.archived]
review_disabled = true
"""
    )

    assert config.schema_version == 1
    assert config.category_policy("price") == ReviewPolicy(ttl=timedelta(hours=24))
    assert config.category_policy("archived") == ReviewPolicy(review_disabled=True)
    assert config.category_policy("missing") is None
    assert config.category_policy(None) is None


@pytest.mark.parametrize("duration", ["0s", "7d", "2w", "15m"])
def test_accepts_supported_duration_units(duration: str) -> None:
    config = parse_policy_toml(
        f'schema_version = 1\n[categories.example]\nttl = "{duration}"\n'
    )
    assert config.category_policy("example") is not None


@pytest.mark.parametrize(
    ("source", "message"),
    [
        ('[categories.example]\nttl = "2d"', "schema_version"),
        ('schema_version = 2\n[categories.example]\nttl = "2d"', "schema_version"),
        ('schema_version = 1\n[categories.example]\nttl = "tomorrow"', "duration"),
        ('schema_version = 1\n[categories.example]\nttl = "-1d"', "duration"),
        (
            'schema_version = 1\n[categories.example]\nttl = "2d"\n'
            "review_disabled = true",
            "choose either",
        ),
        (
            "schema_version = 1\n[categories.example]\nreview_disabled = false",
            "review_disabled",
        ),
        ("schema_version = 1\n[categories.example]\nunknown = true", "Extra inputs"),
        ('schema_version = 1\n[categories.Bad-Key]\nttl = "2d"', "pattern"),
    ],
)
def test_invalid_settings_have_actionable_errors(source: str, message: str) -> None:
    with pytest.raises(PolicyConfigError, match=message):
        parse_policy_toml(source)


def test_policy_categories_are_read_only() -> None:
    config = parse_policy_toml("schema_version = 1\ncategories = {}")
    with pytest.raises(TypeError):
        config.categories["new"] = ReviewPolicy(ttl=timedelta(days=1))  # type: ignore[index]


def test_direct_config_construction_rejects_invalid_data() -> None:
    with pytest.raises(ValueError, match="schema_version"):
        PolicyConfig(categories={}, schema_version=2)

    with pytest.raises(ValueError, match="category name"):
        PolicyConfig(categories={"Bad-Key": ReviewPolicy(ttl=timedelta(days=1))})


def test_load_policy_reads_utf8_file(tmp_path: Path) -> None:
    path = tmp_path / "factttl.toml"
    path.write_text(
        'schema_version = 1\n[categories.law]\nttl = "30d"\n', encoding="utf-8"
    )

    assert load_policy(path).category_policy("law") == ReviewPolicy(
        ttl=timedelta(days=30)
    )


def test_missing_file_error_includes_path(tmp_path: Path) -> None:
    path = tmp_path / "missing.toml"
    with pytest.raises(PolicyConfigError, match="missing.toml"):
        load_policy(path)


def test_malformed_toml_is_reported_as_configuration_error() -> None:
    with pytest.raises(PolicyConfigError, match="Invalid TOML"):
        parse_policy_toml("schema_version = [")


def test_non_utf8_policy_file_is_reported_as_configuration_error(
    tmp_path: Path,
) -> None:
    path = tmp_path / "invalid-encoding.toml"
    path.write_bytes(b"schema_version = 1\n\xff")

    with pytest.raises(PolicyConfigError, match="must be UTF-8"):
        load_policy(path)
