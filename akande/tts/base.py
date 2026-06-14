# Copyright (C) 2026 Sebastien Rousseau.
#
# Licensed under the Apache License, Version 2.0 (the "License").
"""Common types for TTS backends."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class TTSSynthesisResult:
    """Returned by every :class:`TTSBackend` ``synthesise`` call.

    Holds the audio bytes together with the source-of-truth format
    so downstream consumers (watermark, file save, player) can
    avoid re-detection.  ``sample_rate`` is only populated by
    backends that emit raw PCM (e.g. Kokoro); for compressed
    formats it's ``None`` and consumers should decode if they care.
    """

    audio: bytes
    fmt: str  # "mp3" | "wav" | "raw_pcm"
    sample_rate: int | None = None


class TTSBackend(ABC):
    """Render text to speech as bytes.

    Subclasses must set :attr:`name` to a short identifier
    (``gtts``, ``kokoro``, …) so logs / metrics can attribute
    latency to the right backend without leaking provider
    internals.
    """

    name: str = ""

    @abstractmethod
    def synthesise(
        self, text: str, lang: str = "en"
    ) -> TTSSynthesisResult:
        """Synthesise ``text`` in ``lang`` and return audio bytes."""
        ...

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return f"<TTSBackend {self.name}>"
