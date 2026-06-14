# Copyright (C) 2026 Sebastien Rousseau.
#
# Licensed under the Apache License, Version 2.0 (the "License").
"""TTS backend abstraction.

Why does this exist?  The v0.0.5 code path inlined ``gTTS`` calls
directly in :meth:`akande.akande.Akande.speak`.  That worked while
the only synthesis option was gTTS and the only post-processing
was "play it", but:

- Track E's AudioSeal watermark (EU AI Act Article 50 §2) needs to
  see the *bytes* of the synthesised audio before they reach the
  speaker so it can stamp them.  Inline gTTS-then-play makes that
  impossible without monkey-patching.
- Track B's realtime cascade pipeline wants to swap between cloud
  TTS (gTTS) and local TTS (Kokoro / Piper) by environment, with
  no code change at the call site.

So we introduce :class:`TTSBackend` — a tiny ABC with a single
synth method that returns MP3 bytes — and let the caller decide
what to do with them (watermark, save, play, stream).  The default
resolution is gTTS, matching v0.0.5 behaviour exactly when no
other backend is configured.

Configuration
-------------
``AKANDE_TTS`` selects the backend by name (``gtts`` by default;
``kokoro``, ``piper`` reserved for future iterations).  Backends
fail loud if their dependencies are missing — silent fallback to a
different voice would surprise the operator.
"""

from __future__ import annotations

import logging
import os

from .base import TTSBackend, TTSSynthesisResult
from .gtts_backend import GTTSBackend

__all__ = [
    "TTSBackend",
    "TTSSynthesisResult",
    "GTTSBackend",
    "get_tts_backend",
]

logger = logging.getLogger(__name__)


def get_tts_backend(
    name: str | None = None,
) -> TTSBackend:
    """Return a TTS backend resolved from name or ``AKANDE_TTS``.

    Falls back to gTTS if the environment is unset, matching the
    v0.0.5 default.  Unknown names raise ``ValueError`` so a typo
    can't silently route to the wrong voice.
    """
    key = (name or os.getenv("AKANDE_TTS") or "gtts").strip().lower()
    if key == "gtts":
        return GTTSBackend()
    if key == "kokoro":
        from .kokoro_backend import KokoroBackend

        return KokoroBackend()
    raise ValueError(
        f"unknown TTS backend: {key!r} (known: gtts, kokoro)"
    )
