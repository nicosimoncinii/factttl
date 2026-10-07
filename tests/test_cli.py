import json
from io import StringIO
from pathlib import Path

import pytest

from factttl.cli import main


def _document() -> dict[str, object]:
    return {
        "schema_version": 1,
        "evaluation_time": "2026-10-06T12:00:00+02:00",
        "claims": [
            {
                "id": "due",
                "text": "A claim due for review",
                "category": "news",
                "temporal_class": "TIME_SENSITIVE",
                "last_checked_at": "2026-10-04T12:00:00Z",
            },
            {"text": "No applicable policy", "temporal_class": "UNKNOWN"},
        ],
    }


def test_cli_json_output_is_versioned_ordered_and_counts_all_statuses(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    input_path = tmp_path / "claims.json"
    input_path.write_text(json.dumps(_document()), encoding="utf-8")
    policy_path = tmp_path / "policy.toml"
    policy_path.write_text(
        'schema_version = 1\n[categories.news]\nttl = "24h"\n', encoding="utf-8"
    )

    exit_code = main(
        ["scan", str(input_path), "--policy", str(policy_path), "--format", "json"]
    )

    captured = capsys.readouterr()
    result = json.loads(captured.out)
    assert exit_code == 0
    assert captured.err == ""
    assert result["schema_version"] == 1
    assert result["evaluation_time"] == "2026-10-06T10:00:00.000000Z"
    assert [row["id"] for row in result["rows"]] == ["due", "claim-2"]
    assert [row["status"] for row in result["rows"]] == ["STALE", "UNKNOWN"]
    assert result["rows"][0]["policy"]["ttl_seconds"] == 86400
    assert result["total"] == 2
    assert result["counts"] == {
        "FRESH": 0,
        "STALE": 1,
        "UNVERIFIED": 0,
        "NOT_REQUIRED": 0,
        "UNKNOWN": 1,
    }


def test_cli_accepts_stdin_and_text_output(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("sys.stdin", __import__("io").StringIO(json.dumps(_document())))

    exit_code = main(["scan", "-", "--format", "text"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "FactTTL scan at 2026-10-06T10:00:00.000000Z" in captured.out
    assert "UNKNOWN  claim-2" in captured.out
    assert captured.err == ""


def test_cli_reports_invalid_input_to_stderr_and_exits_nonzero(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    input_path = tmp_path / "claims.json"
    input_path.write_text(
        '{"schema_version":1,"evaluation_time":"2026-10-06T12:00:00","claims":[]}',
        encoding="utf-8",
    )

    exit_code = main(["scan", str(input_path), "--format", "json"])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert captured.out == ""
    assert "evaluation_time must include a timezone" in captured.err


def test_cli_rejects_conflicting_claim_override(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    document = _document()
    claims = document["claims"]
    assert isinstance(claims, list)
    claims[0]["ttl_seconds"] = 3600
    claims[0]["review_disabled"] = True
    input_path = tmp_path / "claims.json"
    input_path.write_text(json.dumps(document), encoding="utf-8")

    exit_code = main(["scan", str(input_path)])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "ttl_seconds and review_disabled are mutually exclusive" in captured.err


def test_cli_rejects_duplicate_json_keys(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "sys.stdin",
        StringIO(
            '{"schema_version":1,"schema_version":1,'
            '"evaluation_time":"2026-10-06T12:00:00Z","claims":[]}'
        ),
    )

    exit_code = main(["scan", "-"])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert captured.out == ""
    assert "duplicate JSON key" in captured.err


def test_cli_quotes_multiline_claim_text_in_text_output(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    document = _document()
    claims = document["claims"]
    assert isinstance(claims, list)
    assert isinstance(claims[0], dict)
    claims[0]["text"] = "A claim\nSTALE forged row"
    monkeypatch.setattr("sys.stdin", StringIO(json.dumps(document)))

    exit_code = main(["scan", "-"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert '"A claim\\nSTALE forged row"' in captured.out
    assert "\nSTALE forged row\n" not in captured.out


def test_cli_handles_timestamp_outside_utc_range(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "sys.stdin",
        StringIO(
            '{"schema_version":1,"evaluation_time":"0001-01-01T00:00:00+01:00",'
            '"claims":[]}'
        ),
    )

    exit_code = main(["scan", "-"])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert captured.out == ""
    assert "supported UTC datetime range" in captured.err


def test_cli_rejects_input_over_size_limit(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("sys.stdin", StringIO("x" * (10 * 1024 * 1024 + 1)))

    exit_code = main(["scan", "-"])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert captured.out == ""
    assert "10 MiB size limit" in captured.err
