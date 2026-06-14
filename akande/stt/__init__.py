# Copyright (C) 2026 Sebastien Rousseau.
#
# Licensed under the Apache License, Version 2.0 (the "License").
"""STT backend abstraction — mirrors :mod:`akande.tts`.

Two backends ship today:

- :class:`SpeechRecognitionBackend` — wraps the v0.0.5 path through
  ``speech_recognition``.  Cloud-backed (Google Speech), no extra
  install, exact byte-for-byte behaviour preservation for callers
  that don't opt in to a local backend.
- :class:`FasterWhisperBackend` — wraps ``faster-whisper`` for fully
  local transcription.  Selected with ``AKANDE_STT=faster_whisper``;
  fails loud when the optional dep is missing.

The barge-in + VAD-driven streaming variants land in v0.0.6-dev.8
on top of this same ABC.
"""

from __future__ import annotations

import logging
import os

from .base import STTBackend, STTResult
from .sr_backend import SpeechRecognitionBackend

__all__ = [
    "STTBackend",
    "STTResult",
    "SpeechRecognitionBackend",
    "get_stt_backend",
]

logger = logging.getLogger(__name__)


def get_stt_backend(
    name: str | None = None,
) -> STTBackend:
    """Resolve the active STT backend from name or env."""
    key = (
        (name or os.getenv("AKANDE_STT") or "speech_recognition")
        .strip()
        .lower()
    )
    if key in {"speech_recognition", "sr"}:
        return SpeechRecognitionBackend()
    if key in {"faster_whisper", "whisper"}:
        from .faster_whisper_backend import (
            FasterWhisperBackend,
        )

        return FasterWhisperBackend()
    raise ValueError(
        f"unknown STT backend: {key!r} "
        f"(known: speech_recognition, faster_whisper)"
    )
