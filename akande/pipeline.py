# Copyright (C) 2026 Sebastien Rousseau.
#
# Licensed under the Apache License, Version 2.0 (the "License").
"""Sequential STT → LLM → TTS pipeline.

The minimum viable cascade: read user audio, transcribe, generate
a briefing, synthesise spoken reply, optionally watermark.  No
VAD, no barge-in, no partial-transcript streaming — those land in
v0.0.6-dev.8.  Sequential is still useful because it gives the
CLI / TUI / Web UI one entry point that swaps any of the three
stages by env, and it's the same orchestrator that the S2S
fallback path will reuse.

Configuration
-------------
- ``AKANDE_STT`` — backend (see :mod:`akande.stt`).
- ``AKANDE_TTS`` — backend (see :mod:`akande.tts`).
- ``AKANDE_PROFILE`` — drives watermark + safety envelope.
- ``AKANDE_S2S`` (optional) — if set to a known S2S backend, the
  pipeline routes user audio straight to it and returns the
  reply audio, skipping the cascade entirely.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from akande.profiles import active_profile
from akande.s2s import get_s2s_provider
from akande.stt import get_stt_backend
from akande.tts import get_tts_backend
from akande.watermark import watermark_audio

logger = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    transcript: str
    reply_text: str
    audio: bytes
    fmt: str
    sample_rate: int | None = None
    s2s_used: bool = False
    latency_ms: float = 0.0


def respond_to_audio(
    audio: bytes,
    *,
    fmt: str = "wav",
    sample_rate: int | None = None,
    briefing_fn=None,
) -> PipelineResult:
    """Drive one turn through the configured pipeline.

    ``briefing_fn`` is the only injected dependency — it should
    accept the user's transcript and return the assistant's text.
    The default at call time is a thin closure over the configured
    LLM provider (see :func:`_default_briefing_fn`); tests pass in
    fakes so they don't need network access.
    """
    start = time.time()
    s2s = get_s2s_provider()
    if s2s is not None:
        result = s2s.respond(audio, fmt=fmt, sample_rate=sample_rate)
        latency = (time.time() - start) * 1000
        return PipelineResult(
            transcript=result.transcript or "",
            reply_text="",
            audio=result.audio,
            fmt=result.fmt,
            sample_rate=result.sample_rate,
            s2s_used=True,
            latency_ms=round(latency, 2),
        )

    stt = get_stt_backend()
    stt_result = stt.transcribe(audio, fmt=fmt, sample_rate=sample_rate)
    transcript = stt_result.text

    fn = briefing_fn or _default_briefing_fn
    reply_text = fn(transcript)

    tts = get_tts_backend()
    tts_result = tts.synthesise(reply_text)
    audio_bytes = tts_result.audio
    if active_profile().audio_watermark:
        audio_bytes = watermark_audio(audio_bytes, fmt=tts_result.fmt)
    latency = (time.time() - start) * 1000
    return PipelineResult(
        transcript=transcript,
        reply_text=reply_text,
        audio=audio_bytes,
        fmt=tts_result.fmt,
        sample_rate=tts_result.sample_rate,
        s2s_used=False,
        latency_ms=round(latency, 2),
    )


def _default_briefing_fn(transcript: str) -> str:
    """Call the configured LLM provider for a briefing."""
    from akande.config import OPENAI_DEFAULT_MODEL
    from akande.providers import get_provider
    from akande.services import SYSTEM_PROMPT

    if not transcript.strip():
        return "I couldn't catch that — could you try again?"
    provider = get_provider()
    response = provider.generate_response_sync(
        transcript,
        SYSTEM_PROMPT,
        OPENAI_DEFAULT_MODEL or "gpt-4o-mini",
        None,
    )
    try:
        return str(response.choices[0].message.content or "")
    except (AttributeError, IndexError, TypeError):
        return ""
