"""Bounded local inference profiles; hardware speed is never assumed."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class EngineProfile:
    name: str
    context_tokens: int
    source_chars: int
    prompt_bytes: int
    output_tokens: int
    cpu_only: bool

    def options(self) -> dict[str, int]:
        options = {
            "temperature": 0,
            "num_predict": self.output_tokens,
            "num_ctx": self.context_tokens,
        }
        if self.cpu_only:
            options["num_gpu"] = 0
        return options


_PROFILES = {
    # The byte budget conservatively reserves room for template and response.
    # Oversize inputs must abstain, never silently lose evidence to fit memory.
    "cpu": EngineProfile("cpu", 8192, 2000, 6000, 800, True),
    "balanced": EngineProfile("balanced", 8192, 6000, 6000, 1200, False),
    "extended": EngineProfile("extended", 32768, 12000, 26000, 1600, False),
}


def engine_profile(name: str | None = None) -> EngineProfile:
    selected = (
        name if name is not None else os.environ.get("FACTTTL_NEWS_PROFILE", "balanced")
    )
    if selected not in _PROFILES:
        raise ValueError("Unknown local engine profile")
    return _PROFILES[selected]
