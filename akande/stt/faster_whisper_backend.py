# Copyright (C) 2026 Sebastien Rousseau.
#
# Licensed under the Apache License, Version 2.0 (the "License").
"""faster-whisper local STT backend.

Selected via ``AKANDE_STT=faster_whisper``.  Pulls the ctranslate2
runtime; downloads model weights on first use.  CPU-only by
default; set ``AKANDE_STT_WHISPER_DEVICE=cuda`` to run on GPU.
"""

from __future__ import annotations

import io
import logging
import os
from typing import Any

from .base import STTBackend, STTResult

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "small"


class FasterWhisperBackend(STTBackend):
    name = "faster_whisper"

    def __init__(self) -> None:
        try:
            from faster_whisper import (
                WhisperModel,  # type: ignore[import-not-found]
            )
        except ImportError as exc:  # pragma: no cover
            raise ImportError(
                "faster-whisper is required for the local "
                "Whisper backend.  Install it with: "
                "pip install faster-whisper"
            ) from exc

        # Below runs only when faster-whisper is installed — the
        # optional ``[realtime]`` extra.  Not exercised in CI.
        model_size = os.getenv(  # pragma: no cover
            "AKANDE_STT_WHISPER_MODEL", DEFAULT_MODEL
        )
        device = os.getenv(  # pragma: no cover
            "AKANDE_STT_WHISPER_DEVICE", "cpu"
        )
        compute_type = os.getenv(  # pragma: no cover
            "AKANDE_STT_WHISPER_COMPUTE",
            "int8" if device == "cpu" else "float16",
        )
        self._model: Any = WhisperModel(  # pragma: no cover
            model_size,
            device=device,
            compute_type=compute_type,
        )
        logger.info(  # pragma: no cover
            "faster-whisper STT initialised",
            extra={
                "event": "STT:WhisperInitialised",
                "extra_data": {
                    "model_size": model_size,
                    "device": device,
                    "compute_type": compute_type,
                },
            },
        )

    def transcribe(  # pragma: no cover - needs faster-whisper model
        self,
        audio: bytes,
        *,
        fmt: str = "wav",
        sample_rate: int | None = None,
    ) -> STTResult:
        # faster-whisper accepts a file-like object directly.
        segments, info = self._model.transcribe(
            io.BytesIO(audio),
            beam_size=1,
        )
        text = "".join(s.text for s in segments).strip()
        return STTResult(
            text=text,
            language=getattr(info, "language", None),
            duration_s=getattr(info, "duration", None),
        )
