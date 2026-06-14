# Copyright (C) 2026 Sebastien Rousseau.
#
# Licensed under the Apache License, Version 2.0 (the "License").
"""Speech-to-speech provider seam.

Selected with ``AKANDE_S2S=<name>``; current backends:

- ``openai_realtime`` — :class:`OpenAIRealtimeProvider`
- ``gemini_live``    — :class:`GeminiLiveProvider` (skeleton; full
  driving lands with the realtime cascade pipeline in v0.0.6-dev.8)

Cascade STT→LLM→TTS remains the default for production
deployments; S2S is opt-in.  This module just adds the seam so
operators can experiment without monkey-patching the briefing
path.
"""

from __future__ import annotations

import logging
import os

from .base import S2SProvider, S2SResult
from .openai_realtime import OpenAIRealtimeProvider

__all__ = [
    "S2SProvider",
    "S2SResult",
    "OpenAIRealtimeProvider",
    "get_s2s_provider",
]

logger = logging.getLogger(__name__)


def get_s2s_provider(
    name: str | None = None,
) -> S2SProvider | None:
    """Resolve an S2S backend by name or env; ``None`` when unset.

    Returning ``None`` rather than raising means callers can write
    ``provider = get_s2s_provider()`` and short-circuit cascade
    fallback without a try/except.
    """
    key = (name or os.getenv("AKANDE_S2S") or "").strip().lower()
    if not key:
        return None
    if key in {"openai_realtime", "openai", "realtime"}:
        return OpenAIRealtimeProvider()
    if key in {"gemini_live", "gemini", "live"}:
        from .gemini_live import GeminiLiveProvider

        return GeminiLiveProvider()
    raise ValueError(
        f"unknown S2S provider: {key!r} "
        f"(known: openai_realtime, gemini_live)"
    )
