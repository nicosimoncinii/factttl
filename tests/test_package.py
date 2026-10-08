import os
import subprocess
import sys
from pathlib import Path


def test_package_is_importable() -> None:
    import factttl

    assert factttl.__name__ == "factttl"


def test_public_api_exports_core_config_and_report_symbols() -> None:
    import factttl

    expected = {
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
    }

    assert set(factttl.__all__) == expected
    assert all(hasattr(factttl, name) for name in expected)
    assert not any("mcp" in name.lower() for name in factttl.__all__)


def test_freshness_import_does_not_load_pydantic() -> None:
    repository = Path(__file__).resolve().parents[1]
    script = """
import importlib.abc
import sys

class BlockPydantic(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == 'pydantic' or fullname.startswith('pydantic.'):
            raise AssertionError('freshness core imported Pydantic')
        return None

sys.meta_path.insert(0, BlockPydantic())
from factttl.freshness import FreshnessStatus
assert FreshnessStatus.FRESH.value == 'FRESH'
"""
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(repository / "src")
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=repository,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
