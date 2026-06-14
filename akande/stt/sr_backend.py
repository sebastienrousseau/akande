# Copyright (C) 2026 Sebastien Rousseau.
#
# Licensed under the Apache License, Version 2.0 (the "License").
"""speech_recognition backend — the v0.0.5 default behind the ABC."""

from __future__ import annotations

import io
import logging

from .base import STTBackend, STTResult

logger = logging.getLogger(__name__)


class SpeechRecognitionBackend(STTBackend):
    name = "speech_recognition"

    def transcribe(
        self,
        audio: bytes,
        *,
        fmt: str = "wav",
        sample_rate: int | None = None,
    ) -> STTResult:
        import speech_recognition as sr

        recogniser = sr.Recognizer()
        # speech_recognition expects an AudioFile pointing at a
        # readable WAV/AIFF/FLAC stream.  pydub does the conversion
        # if the caller hands us anything else.
        if fmt == "wav":
            audio_data = audio
        else:
            from pydub import AudioSegment

            seg = AudioSegment.from_file(io.BytesIO(audio), format=fmt)
            buf = io.BytesIO()
            seg.export(buf, format="wav")
            audio_data = buf.getvalue()
        with sr.AudioFile(io.BytesIO(audio_data)) as source:
            captured = recogniser.record(source)
        try:
            text = recogniser.recognize_google(captured)
        except sr.UnknownValueError:
            text = ""
        except sr.RequestError as exc:
            logger.warning(
                "speech_recognition request failed: %s",
                exc,
                extra={
                    "event": "STT:RequestFailed",
                },
            )
            text = ""
        return STTResult(text=text, language="en")
