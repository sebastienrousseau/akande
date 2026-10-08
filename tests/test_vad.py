# Copyright (C) 2026 Sebastien Rousseau.
#
# Licensed under the Apache License, Version 2.0 (the "License").
"""Unit tests for VoiceActivityDetector and barge-in triggers."""

import struct

from akande.stt.vad import VoiceActivityDetector


def _generate_pcm16_chunk(amplitude: int, count: int = 480) -> bytes:
    """Generate raw 16-bit signed PCM samples with given amplitude."""
    return struct.pack(f"<{count}h", *([amplitude] * count))


class TestVoiceActivityDetector:
    def test_init_defaults(self):
        vad = VoiceActivityDetector()
        assert vad.sample_rate == 16000
        assert vad.energy_threshold == 0.02
        assert not vad.is_interrupted()
        assert vad.average_recent_energy() == 0.0

    def test_calculate_rms_empty_or_too_short(self):
        vad = VoiceActivityDetector()
        assert vad.calculate_rms(b"") == 0.0
        assert vad.calculate_rms(b"\x00") == 0.0

    def test_calculate_rms_silence(self):
        vad = VoiceActivityDetector()
        chunk = _generate_pcm16_chunk(0, 480)
        assert vad.calculate_rms(chunk) == 0.0
        assert vad.is_speech(chunk) is False

    def test_calculate_rms_max_amplitude(self):
        vad = VoiceActivityDetector()
        chunk = _generate_pcm16_chunk(32767, 480)
        rms = vad.calculate_rms(chunk)
        assert rms > 0.99
        assert vad.is_speech(chunk) is True

    def test_odd_byte_length_handled(self):
        vad = VoiceActivityDetector()
        chunk = _generate_pcm16_chunk(1000, 100) + b"\x00"
        rms = vad.calculate_rms(chunk)
        assert rms > 0.0

    def test_barge_in_trigger_and_reset(self):
        vad = VoiceActivityDetector(energy_threshold=0.05)
        assert not vad.is_interrupted()

        # Silence chunk should not trigger barge-in
        silence = _generate_pcm16_chunk(100, 480)
        triggered = vad.process_barge_in(silence)
        assert triggered is False
        assert not vad.is_interrupted()

        # Loud chunk triggers barge-in
        loud = _generate_pcm16_chunk(25000, 480)
        triggered = vad.process_barge_in(loud)
        assert triggered is True
        assert vad.is_interrupted()

        # Resetting clears the event
        vad.reset_barge_in()
        assert not vad.is_interrupted()

    def test_rolling_average_energy(self):
        vad = VoiceActivityDetector(history_frames=5)
        for _ in range(5):
            vad.is_speech(_generate_pcm16_chunk(16384, 480))
        avg = vad.average_recent_energy()
        assert 0.4 < avg < 0.6
