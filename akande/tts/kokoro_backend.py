# Copyright (C) 2026 Sebastien Rousseau.
#
# Licensed under the Apache License, Version 2.0 (the "License").
"""Kokoro-82M local TTS backend.

Kokoro is the smallest of the credible 2026 OSS TTS models — sub-
300 ms synthesis on a Mac CPU, no GPU required, MIT-licensed.
This backend wraps ``kokoro-onnx`` so Àkàndé can run fully offline
together with Ollama for the LLM and faster-whisper for the STT.

Activation
----------
``pip install akande[tts-local]`` (or ``pip install kokoro-onnx``
directly) installs the runtime.  Selecting Kokoro with
``AKANDE_TTS=kokoro`` while the package is missing raises a
helpful ``ImportError`` rather than silently falling back to gTTS
— a wrong voice is a worse failure mode than a clear error.

The model weights download lazily on first use under
``$KOKORO_MODEL_HOME`` (default ``~/.akande/models/kokoro``); set
``AKANDE_TTS_KOKORO_VOICE`` to pick a non-default voice (e.g.
``af_sky``, ``am_michael``).
"""

from __future__ import annotations

import io
import logging
import os
from pathlib import Path
from typing import Any

from .base import TTSBackend, TTSSynthesisResult

logger = logging.getLogger(__name__)

DEFAULT_VOICE = "af_sky"
DEFAULT_SAMPLE_RATE = 24_000


class KokoroBackend(TTSBackend):
    name = "kokoro"

    def __init__(
        self,
        voice: str | None = None,
        model_path: str | None = None,
    ) -> None:
        try:
            from kokoro_onnx import (
                Kokoro,  # type: ignore[import-not-found]
            )
        except ImportError as exc:  # pragma: no cover
            raise ImportError(
                "kokoro-onnx is required for the Kokoro TTS "
                "backend.  Install it with: "
                "pip install kokoro-onnx"
            ) from exc

        # The body below only executes when kokoro-onnx is installed,
        # which is an optional extra (akande[tts-local]).  In CI it
        # isn't installed, so the import above raises and the rest
        # never runs.  The integration runs on a developer machine.
        self._voice = (  # pragma: no cover
            voice
            or os.getenv("AKANDE_TTS_KOKORO_VOICE")
            or DEFAULT_VOICE
        )
        self._model_path = (
            model_path or self._resolve_model_path()
        )  # pragma: no cover
        self._client: Any = Kokoro(  # pragma: no cover
            model_path=self._model_path,
            voices_path=self._resolve_voices_path(),
        )
        logger.info(  # pragma: no cover
            "Kokoro TTS backend initialised",
            extra={
                "event": "TTS:KokoroInitialised",
                "extra_data": {
                    "voice": self._voice,
                    "model_path": self._model_path,
                },
            },
        )

    def _resolve_model_path(
        self,
    ) -> str:  # pragma: no cover - tested via integration
        home = os.getenv(
            "KOKORO_MODEL_HOME",
            str(Path.home() / ".akande" / "models" / "kokoro"),
        )
        return str(Path(home) / "kokoro-v1.0.onnx")

    def _resolve_voices_path(
        self,
    ) -> str:  # pragma: no cover - tested via integration
        home = os.getenv(
            "KOKORO_MODEL_HOME",
            str(Path.home() / ".akande" / "models" / "kokoro"),
        )
        return str(Path(home) / "voices-v1.0.bin")

    def synthesise(  # pragma: no cover - needs kokoro-onnx
        self, text: str, lang: str = "en"
    ) -> TTSSynthesisResult:
        # Kokoro returns raw PCM + sample rate.  We encode to WAV
        # in memory so the caller has a self-describing artefact
        # (with a header) that pydub / AudioSeal can ingest.
        samples, sample_rate = self._client.create(
            text,
            voice=self._voice,
            speed=1.0,
            lang=lang or "en-us",
        )
        wav_bytes = _pcm_float_to_wav_bytes(samples, sample_rate)
        return TTSSynthesisResult(
            audio=wav_bytes,
            fmt="wav",
            sample_rate=sample_rate,
        )


def _pcm_float_to_wav_bytes(  # pragma: no cover - needs numpy + kokoro
    samples: Any, sample_rate: int
) -> bytes:
    """Encode a float32 PCM array as a 16-bit WAV without numpy hard-dep.

    Kokoro returns numpy arrays; we wrap the import here so the
    rest of the codebase doesn't pay for numpy at import time.
    """
    import wave

    import numpy as np  # type: ignore[import-not-found]

    arr = np.asarray(samples, dtype=np.float32)
    pcm16 = (arr * 32767.0).clip(-32768, 32767).astype(np.int16)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(pcm16.tobytes())
    return buf.getvalue()
