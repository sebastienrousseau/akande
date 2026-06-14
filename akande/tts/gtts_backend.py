# Copyright (C) 2026 Sebastien Rousseau.
#
# Licensed under the Apache License, Version 2.0 (the "License").
"""gTTS backend — the v0.0.5 default, now behind the abstraction.

Returns MP3 bytes via the in-memory ``write_to_fp`` path so the
caller can watermark / save / stream them without a round trip
through disk.
"""

from __future__ import annotations

import io
import logging

from .base import TTSBackend, TTSSynthesisResult

logger = logging.getLogger(__name__)


class GTTSBackend(TTSBackend):
    name = "gtts"

    def __init__(self, lang: str = "en", tld: str = "co.uk") -> None:
        self._default_lang = lang
        self._tld = tld

    def synthesise(
        self, text: str, lang: str = "en"
    ) -> TTSSynthesisResult:
        from gtts import gTTS

        buf = io.BytesIO()
        tts = gTTS(
            text=text,
            lang=lang or self._default_lang,
            tld=self._tld,
        )
        tts.write_to_fp(buf)
        data = buf.getvalue()
        logger.debug(
            "gTTS synthesis returned %d bytes for %d chars",
            len(data),
            len(text),
        )
        return TTSSynthesisResult(audio=data, fmt="mp3")
