# Copyright (C) 2026 Sebastien Rousseau.
#
# Licensed under the Apache License, Version 2.0 (the "License").
"""Common types for STT backends."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class STTResult:
    """Returned by every :class:`STTBackend` ``transcribe`` call."""

    text: str
    language: str | None = None
    duration_s: float | None = None


class STTBackend(ABC):
    """Transcribe audio bytes to text."""

    name: str = ""

    @abstractmethod
    def transcribe(
        self,
        audio: bytes,
        *,
        fmt: str = "wav",
        sample_rate: int | None = None,
    ) -> STTResult:
        """Transcribe ``audio`` and return the recognised text."""
        ...

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return f"<STTBackend {self.name}>"
