# Copyright (C) 2026 Sebastien Rousseau.
#
# Licensed under the Apache License, Version 2.0 (the "License").
"""Voice Activity Detection (VAD) and real-time barge-in detector.

Exposes a streaming VoiceActivityDetector for energy-based speech
detection on raw PCM-16 audio frames without external binary dependencies.
Supports immediate barge-in signalling when user speech energy crosses
a threshold during assistant speech output.
"""

from __future__ import annotations

import asyncio
import math
import struct
from collections import deque


class VoiceActivityDetector:
    """Real-time energy-based voice activity detector with barge-in support."""

    def __init__(
        self,
        sample_rate: int = 16000,
        frame_duration_ms: int = 30,
        energy_threshold: float = 0.02,
        history_frames: int = 10,
    ) -> None:
        self.sample_rate = sample_rate
        self.frame_duration_ms = frame_duration_ms
        self.energy_threshold = energy_threshold
        self.bytes_per_frame = int(
            sample_rate * (frame_duration_ms / 1000.0) * 2
        )
        self._history: deque[float] = deque(maxlen=history_frames)
        self._interrupted = asyncio.Event()

    def calculate_rms(self, pcm_chunk: bytes) -> float:
        """Calculate Root-Mean-Square (RMS) normalized energy in range [0.0, 1.0]."""
        if not pcm_chunk or len(pcm_chunk) < 2:
            return 0.0
        aligned_len = len(pcm_chunk) - (len(pcm_chunk) % 2)
        num_samples = aligned_len // 2
        if num_samples == 0:
            return 0.0
        try:
            samples = struct.unpack(
                f"<{num_samples}h", pcm_chunk[:aligned_len]
            )
        except struct.error:  # pragma: no cover - defensively guarded
            return 0.0
        sum_squares = sum(s * s for s in samples)
        rms = math.sqrt(sum_squares / num_samples)
        return min(rms / 32768.0, 1.0)

    def is_speech(self, pcm_chunk: bytes) -> bool:
        """Evaluate whether a PCM chunk contains speech."""
        rms = self.calculate_rms(pcm_chunk)
        self._history.append(rms)
        return rms >= self.energy_threshold

    def process_barge_in(self, pcm_chunk: bytes) -> bool:
        """Process chunk and set barge-in interruption flag if speech is detected."""
        if self.is_speech(pcm_chunk):
            self._interrupted.set()
            return True
        return False

    def is_interrupted(self) -> bool:
        """Check if barge-in has been triggered."""
        return self._interrupted.is_set()

    def reset_barge_in(self) -> None:
        """Reset the barge-in flag for the next turn."""
        self._interrupted.clear()

    def average_recent_energy(self) -> float:
        """Return rolling average energy over history window."""
        if not self._history:
            return 0.0
        return sum(self._history) / len(self._history)
