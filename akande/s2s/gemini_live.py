# Copyright (C) 2026 Sebastien Rousseau.
#
# Licensed under the Apache License, Version 2.0 (the "License").
"""Gemini Live S2S provider — skeleton.

The Gemini Live API has a comparable WebSocket protocol; full
implementation lands with the realtime cascade pipeline in
v0.0.6-dev.8.  This skeleton lets operators set
``AKANDE_S2S=gemini_live`` today and get a clear ``NotImplemented``
rather than a vague AttributeError.
"""

from __future__ import annotations

from .base import S2SProvider, S2SResult


class GeminiLiveProvider(S2SProvider):
    name = "gemini_live"

    def respond(
        self,
        audio: bytes,
        *,
        fmt: str = "wav",
        sample_rate: int | None = None,
    ) -> S2SResult:
        raise NotImplementedError(
            "GeminiLiveProvider lands in v0.0.6-dev.8 — set "
            "AKANDE_S2S=openai_realtime for now, or fall back "
            "to the cascade pipeline by unsetting AKANDE_S2S."
        )
