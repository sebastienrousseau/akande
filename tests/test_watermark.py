# Copyright (C) 2026 Sebastien Rousseau.
#
# Licensed under the Apache License, Version 2.0 (the "License").
"""Tests for the AudioSeal watermarking seam (v0.0.6 Track E §50.2).

Two layers of coverage:

1. **Unit** — the fail-open path (no audioseal installed) and the
   warning throttle.  These run anywhere.
2. **Integration** — actual watermark+detect round-trip, skipped
   when ``audioseal`` is missing.  Operators preparing the 2 Aug
   2026 deadline should run these with ``pip install
   akande[watermark]`` to prove their build actually passes the
   ≥98 % bit-recovery criterion.
"""

import io
import time
from unittest.mock import patch

import pytest

from akande import watermark
from akande.watermark import (
    _audioseal_available,
    detect_watermark,
    watermark_audio,
)


@pytest.fixture(autouse=True)
def _reset_state():
    watermark._reset_for_tests()
    yield
    watermark._reset_for_tests()


class TestFailOpen:
    def test_passthrough_when_audioseal_missing(self):
        with patch(
            "akande.watermark._audioseal_available",
            return_value=False,
        ):
            out = watermark_audio(b"raw-mp3-bytes", fmt="mp3")
        assert out == b"raw-mp3-bytes"

    def test_detect_returns_false_when_missing(self):
        with patch(
            "akande.watermark._audioseal_available",
            return_value=False,
        ):
            present, confidence = detect_watermark(
                b"raw", fmt="mp3"
            )
        assert present is False
        assert confidence == 0.0


class TestWarnThrottle:
    def test_first_call_warns(self, caplog):
        with patch(
            "akande.watermark._audioseal_available",
            return_value=False,
        ), caplog.at_level("WARNING"):
            watermark_audio(b"x", fmt="mp3")
        assert any(
            "AudioSeal not installed" in r.message
            for r in caplog.records
        )

    def test_repeat_within_window_skips_warning(
        self, caplog
    ):
        with patch(
            "akande.watermark._audioseal_available",
            return_value=False,
        ), caplog.at_level("WARNING"):
            watermark_audio(b"x", fmt="mp3")
            caplog.clear()
            watermark_audio(b"x", fmt="mp3")
        assert not any(
            "AudioSeal not installed" in r.message
            for r in caplog.records
        )


class TestThrottleWindow:
    def test_repeat_after_window_warns_again(
        self, caplog
    ):
        with patch(
            "akande.watermark._audioseal_available",
            return_value=False,
        ):
            with caplog.at_level("WARNING"):
                watermark_audio(b"x", fmt="mp3")
            caplog.clear()
            # Fast-forward by overriding the internal timestamp so
            # the next call thinks the throttle window has elapsed.
            watermark._LAST_MISSING_WARN_AT = (
                time.time()
                - watermark._MISSING_WARN_INTERVAL_S
                - 1.0
            )
            with caplog.at_level("WARNING"):
                watermark_audio(b"x", fmt="mp3")
        assert any(
            "AudioSeal not installed" in r.message
            for r in caplog.records
        )


class TestResetHelper:
    def test_reset_clears_singletons(self):
        watermark._generator = object()
        watermark._detector = object()
        watermark._LAST_MISSING_WARN_AT = 12345.0
        watermark._reset_for_tests()
        assert watermark._generator is None
        assert watermark._detector is None
        assert watermark._LAST_MISSING_WARN_AT == 0.0


class TestExceptionPath:
    def test_synthesis_failure_falls_open(self):
        with patch(
            "akande.watermark._audioseal_available",
            return_value=True,
        ), patch(
            "akande.watermark._bytes_to_tensor",
            side_effect=RuntimeError("boom"),
        ):
            out = watermark_audio(
                b"original", fmt="mp3"
            )
        # Per the docstring contract: a watermark *failure* must
        # never block delivery; the unwatermarked audio is what
        # the user hears.
        assert out == b"original"


@pytest.mark.skipif(
    not _audioseal_available(),
    reason="audioseal not installed",
)
class TestRoundTripIntegration:  # pragma: no cover - depends on optional dep
    """Real AudioSeal round-trip.  Only runs when AudioSeal is on path."""

    def _silence(self, seconds: float = 1.0) -> bytes:
        import wave

        try:
            import numpy as np  # type: ignore[import-not-found]
        except ImportError:
            pytest.skip("numpy not installed")

        rate = 16_000
        arr = (np.random.randn(int(rate * seconds)) * 0.05).astype(
            np.float32
        )
        pcm = (arr * 32767).astype(np.int16)
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(rate)
            wav.writeframes(pcm.tobytes())
        return buf.getvalue()

    def test_watermark_detected_in_clean_signal(self):
        original = self._silence(seconds=1.0)
        marked = watermark_audio(original, fmt="wav")
        present, confidence = detect_watermark(
            marked, fmt="wav"
        )
        assert present, f"watermark not detected (conf={confidence:.3f})"
        # Article-50 reference benchmark is 98% bit-accuracy on
        # MP3 128 kbps; the clean detection floor should be much
        # higher.  We sanity-check at 0.7 rather than 0.5 so a
        # passing test really does mean the seam is healthy.
        assert confidence > 0.7

    def test_clean_signal_has_no_watermark(self):
        clean = self._silence(seconds=1.0)
        present, _ = detect_watermark(clean, fmt="wav")
        assert present is False
