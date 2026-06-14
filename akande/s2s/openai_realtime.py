# Copyright (C) 2026 Sebastien Rousseau.
#
# Licensed under the Apache License, Version 2.0 (the "License").
"""OpenAI Realtime API speech-to-speech provider.

Uses the WebSocket-based Realtime API (gpt-realtime model family).
Today's implementation transcribes + replies in one round trip; a
streaming variant with partial deltas + barge-in lands with the
realtime cascade pipeline in v0.0.6-dev.8.

Activation
----------
``AKANDE_S2S=openai_realtime`` plus ``OPENAI_API_KEY``.
``AKANDE_S2S_VOICE`` selects the TTS voice (default ``alloy``).
``AKANDE_S2S_MODEL`` overrides the model id (default
``gpt-realtime``).
"""

from __future__ import annotations

import base64
import logging
import os
from typing import Any

from .base import S2SProvider, S2SResult

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "gpt-realtime"
DEFAULT_VOICE = "alloy"


class OpenAIRealtimeProvider(S2SProvider):
    name = "openai_realtime"

    def __init__(self) -> None:
        api_key = os.getenv("OPENAI_API_KEY", "")
        if not api_key:
            raise ValueError(
                "OPENAI_API_KEY is required for the OpenAI "
                "Realtime S2S provider."
            )
        self._api_key = (
            api_key  # pragma: no cover - needs OPENAI_API_KEY env
        )
        self._model = os.getenv(  # pragma: no cover
            "AKANDE_S2S_MODEL", DEFAULT_MODEL
        )
        self._voice = os.getenv(  # pragma: no cover
            "AKANDE_S2S_VOICE", DEFAULT_VOICE
        )

    def respond(  # pragma: no cover - opens a real websocket
        self,
        audio: bytes,
        *,
        fmt: str = "wav",
        sample_rate: int | None = None,
    ) -> S2SResult:
        try:
            import websockets.sync.client as ws  # type: ignore[import-not-found]
        except ImportError as exc:
            raise ImportError(
                "websockets is required for the OpenAI Realtime "
                "provider.  Install with: pip install websockets"
            ) from exc

        url = "wss://api.openai.com/v1/realtime?model=" + self._model
        headers = [
            ("Authorization", f"Bearer {self._api_key}"),
            ("OpenAI-Beta", "realtime=v1"),
        ]
        encoded = base64.b64encode(audio).decode("ascii")
        text_parts: list[str] = []
        audio_chunks: list[bytes] = []
        with ws.connect(url, additional_headers=headers) as conn:
            conn.send(
                _envelope(
                    "session.update",
                    session={
                        "voice": self._voice,
                        "modalities": ["text", "audio"],
                    },
                )
            )
            conn.send(
                _envelope(
                    "input_audio_buffer.append",
                    audio=encoded,
                )
            )
            conn.send(_envelope("input_audio_buffer.commit"))
            conn.send(_envelope("response.create"))
            for raw in conn:
                event = _decode(raw)
                etype = event.get("type", "")
                if etype.endswith("audio.delta"):
                    audio_chunks.append(
                        base64.b64decode(event["delta"])
                    )
                elif etype.endswith("audio_transcript.delta"):
                    text_parts.append(str(event.get("delta", "")))
                elif etype == "response.done":
                    break
                elif etype == "error":
                    raise RuntimeError(
                        f"OpenAI Realtime error: {event.get('error')}"
                    )
        return S2SResult(
            audio=b"".join(audio_chunks),
            fmt="raw_pcm",
            transcript="".join(text_parts) or None,
            sample_rate=24_000,
        )


def _envelope(event_type: str, **fields: Any) -> str:
    import json

    return json.dumps({"type": event_type, **fields})


def _decode(raw: Any) -> dict:
    import json

    if isinstance(raw, (bytes, bytearray)):
        raw = raw.decode("utf-8", errors="replace")
    return json.loads(raw)
