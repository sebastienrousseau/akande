# Copyright (C) 2026 Sebastien Rousseau.
#
# Licensed under the Apache License, Version 2.0 (the "License").
"""Common types for speech-to-speech providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class S2SResult:
    """Returned by :meth:`S2SProvider.respond`."""

    audio: bytes
    fmt: str  # "wav" | "mp3" | "raw_pcm"
    transcript: str | None = None
    sample_rate: int | None = None


class S2SProvider(ABC):
    """End-to-end speech-to-speech provider.

    The interface is deliberately bytes-in / bytes-out so the
    realtime cascade pipeline (v0.0.6-dev.8) can swap in a real
    WebSocket-driven implementation without changing the call
    site.  Today's implementations may load the entire reply
    before returning — streaming arrives with the pipeline.
    """

    name: str = ""

    @abstractmethod
    def respond(
        self,
        audio: bytes,
        *,
        fmt: str = "wav",
        sample_rate: int | None = None,
    ) -> S2SResult:
        """Take user audio, return assistant audio."""
        ...

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return f"<S2SProvider {self.name}>"
