import pytest

from factttl.engine_profile import engine_profile


def test_balanced_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FACTTTL_NEWS_PROFILE", raising=False)
    assert engine_profile().context_tokens == 8192
    assert "num_gpu" not in engine_profile().options()


def test_cpu_is_explicit_and_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FACTTTL_NEWS_PROFILE", "cpu")
    profile = engine_profile()
    assert profile.options()["num_gpu"] == 0
    assert profile.source_chars == 2000
    assert profile.prompt_bytes + profile.output_tokens < profile.context_tokens


@pytest.mark.parametrize("name", ["", "auto", "gpu", "CPU", "cloud"])
def test_unknown_profile_fails_closed(name: str) -> None:
    with pytest.raises(ValueError):
        engine_profile(name)


def test_explicit_overrides_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FACTTTL_NEWS_PROFILE", "invalid")
    assert engine_profile("extended").context_tokens == 32768
