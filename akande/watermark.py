# Copyright (C) 2026 Sebastien Rousseau.
#
# Licensed under the Apache License, Version 2.0 (the "License").
"""AudioSeal-based audio watermarking (EU AI Act Article 50 §2).

Article 50 §2 (binding 2 August 2026) requires that synthetic
audio be marked "in a machine-readable form" so downstream tools
can detect AI-generated content even after lossy re-encoding.
AudioSeal is Meta's MIT-licensed implementation; it embeds a
neural watermark resistant to MP3 128 kbps round-trips with
≥98 % bit-accuracy in the reference benchmark.

This module is the seam.  When the active profile demands
watermarking (``eu`` and ``strict``) every TTS output goes through
:func:`watermark_audio` before reaching the speaker, the disk, or
the SSE channel.  When ``audioseal`` is not installed, the seam
*passes audio through unchanged* and logs a warning every 60 s so
the operator sees the gap without the system going down.  This
fail-open posture is deliberate: a silent product is worse than an
unwatermarked one, and operators relying on the legal control
should configure their deployment to install ``audioseal``.

Usage
-----
::

    from akande.watermark import watermark_audio, detect_watermark

    wm_bytes = watermark_audio(mp3_bytes, fmt="mp3")
    present, confidence = detect_watermark(wm_bytes, fmt="mp3")

Backends
--------
The module supports MP3, WAV, and raw PCM ``bytes`` inputs.  All
heavy decode/encode work happens behind ``pydub`` (already a
project dep), so the only AudioSeal-specific dependency is
``audioseal`` itself.
"""

from __future__ import annotations

import io
import logging
import threading
import time
from typing import Any

logger = logging.getLogger(__name__)

# AudioSeal's reference generator operates at 16 kHz mono.  We
# resample on entry / exit so the rest of Àkàndé can keep using
# whatever sample rate the TTS backend produces.
WATERMARK_SAMPLE_RATE = 16_000

# Throttle "audioseal not installed" warnings so a busy stream
# doesn't flood the log.
_LAST_MISSING_WARN_AT = 0.0
_MISSING_WARN_INTERVAL_S = 60.0
_lock = threading.Lock()

# Lazy-loaded model singletons.
_generator: Any = None
_detector: Any = None


def _audioseal_available() -> bool:
    try:
        import audioseal  # noqa: F401
    except ImportError:
        return False
    return True


def _warn_missing_throttled() -> None:
    """Log the missing-AudioSeal warning at most once per minute."""
    global _LAST_MISSING_WARN_AT
    with _lock:
        now = time.time()
        if now - _LAST_MISSING_WARN_AT < _MISSING_WARN_INTERVAL_S:
            return
        _LAST_MISSING_WARN_AT = now
    logger.warning(
        "AudioSeal not installed — TTS output is NOT watermarked. "
        "Install with: pip install audioseal",
        extra={"event": "Watermark:Missing"},
    )


def _get_generator() -> Any:  # pragma: no cover - needs audioseal
    global _generator
    if _generator is not None:
        return _generator
    from audioseal import AudioSeal  # type: ignore[import-not-found]

    _generator = AudioSeal.load_generator("audioseal_wm_16bits")
    return _generator


def _get_detector() -> Any:  # pragma: no cover - needs audioseal
    global _detector
    if _detector is not None:
        return _detector
    from audioseal import AudioSeal  # type: ignore[import-not-found]

    _detector = AudioSeal.load_detector("audioseal_detector_16bits")
    return _detector


def _bytes_to_tensor(  # pragma: no cover - needs audioseal + torch
    data: bytes, fmt: str
) -> tuple[Any, int]:
    """Decode arbitrary audio bytes to a (1, 1, samples) torch tensor.

    Returns the tensor and the *original* sample rate so the caller
    can re-encode with the same rate.
    """
    import torch  # type: ignore[import-not-found]
    from pydub import AudioSegment

    if fmt == "raw_pcm":
        # Caller knows the rate — they should have packaged it as
        # WAV before calling.  For safety we treat as 16 kHz mono.
        audio = AudioSegment(
            data=data,
            sample_width=2,
            frame_rate=WATERMARK_SAMPLE_RATE,
            channels=1,
        )
    else:
        audio = AudioSegment.from_file(io.BytesIO(data), format=fmt)
    audio = audio.set_channels(1)
    samples = audio.get_array_of_samples()
    import numpy as np  # type: ignore[import-not-found]

    arr = np.array(samples, dtype=np.float32) / float(
        1 << (8 * audio.sample_width - 1)
    )
    tensor = torch.from_numpy(arr).unsqueeze(0).unsqueeze(0)
    return tensor, audio.frame_rate


def _tensor_to_bytes(  # pragma: no cover - needs torch
    tensor: Any, sample_rate: int, fmt: str
) -> bytes:
    """Re-encode a (1, 1, samples) float tensor to ``fmt`` bytes."""
    import numpy as np  # type: ignore[import-not-found]
    from pydub import AudioSegment

    arr = tensor.squeeze().detach().cpu().numpy()
    pcm16 = (arr * 32767.0).clip(-32768, 32767).astype(np.int16)
    audio = AudioSegment(
        data=pcm16.tobytes(),
        sample_width=2,
        frame_rate=sample_rate,
        channels=1,
    )
    buf = io.BytesIO()
    audio.export(buf, format=fmt)
    return buf.getvalue()


def watermark_audio(
    audio: bytes,
    *,
    fmt: str = "mp3",
) -> bytes:
    """Embed an AudioSeal watermark in ``audio`` and return new bytes.

    Returns the input unchanged when ``audioseal`` is not
    installed.  The output format matches the input format so
    callers can drop the result into the same downstream pipeline
    (player, save, SSE) without a re-encode.
    """
    if not _audioseal_available():
        _warn_missing_throttled()
        return audio
    try:
        # The AudioSeal-driven branch needs torch + audioseal +
        # torchaudio installed, none of which run in the default
        # CI environment.  The integration tests under
        # tests/test_watermark.py::TestRoundTripIntegration
        # exercise this path on a developer machine that has the
        # extras installed.
        import torchaudio.functional as F  # type: ignore[import-not-found]  # pragma: no cover

        tensor, sample_rate = _bytes_to_tensor(
            audio, fmt
        )  # pragma: no cover
        if sample_rate != WATERMARK_SAMPLE_RATE:  # pragma: no cover
            tensor = F.resample(
                tensor.squeeze(0),
                sample_rate,
                WATERMARK_SAMPLE_RATE,
            ).unsqueeze(0)
            working_rate = WATERMARK_SAMPLE_RATE
        else:  # pragma: no cover
            working_rate = sample_rate
        gen = _get_generator()  # pragma: no cover
        watermark = gen.get_watermark(  # pragma: no cover
            tensor, sample_rate=working_rate
        )
        wm_tensor = tensor + watermark  # pragma: no cover
        if sample_rate != WATERMARK_SAMPLE_RATE:  # pragma: no cover
            wm_tensor = F.resample(
                wm_tensor.squeeze(0),
                WATERMARK_SAMPLE_RATE,
                sample_rate,
            ).unsqueeze(0)
        return _tensor_to_bytes(  # pragma: no cover
            wm_tensor, sample_rate, fmt
        )
    except Exception as exc:
        logger.error(
            "Watermark application failed; passing audio "
            "through unwatermarked",
            exc_info=True,
            extra={
                "event": "Watermark:Failed",
                "extra_data": {
                    "error": type(exc).__name__,
                },
            },
        )
        return audio


def detect_watermark(
    audio: bytes,
    *,
    fmt: str = "mp3",
) -> tuple[bool, float]:
    """Return ``(present, confidence)`` for ``audio``.

    ``present`` is ``True`` when the mean detector probability over
    the audio exceeds 0.5; ``confidence`` is the mean probability
    so callers can apply their own threshold.  When AudioSeal is
    not installed, returns ``(False, 0.0)`` so verify CLIs print
    a clear "no watermark" result rather than crashing.
    """
    if not _audioseal_available():
        return False, 0.0
    try:
        import torchaudio.functional as F  # type: ignore[import-not-found]  # pragma: no cover

        tensor, sample_rate = _bytes_to_tensor(
            audio, fmt
        )  # pragma: no cover
        if sample_rate != WATERMARK_SAMPLE_RATE:  # pragma: no cover
            tensor = F.resample(
                tensor.squeeze(0),
                sample_rate,
                WATERMARK_SAMPLE_RATE,
            ).unsqueeze(0)
        detector = _get_detector()  # pragma: no cover
        result, _ = detector.detect_watermark(  # pragma: no cover
            tensor, sample_rate=WATERMARK_SAMPLE_RATE
        )
        confidence = float(result.mean().item())  # pragma: no cover
        return confidence > 0.5, confidence  # pragma: no cover
    except Exception as exc:
        logger.error(
            "Watermark detection failed",
            exc_info=True,
            extra={
                "event": "Watermark:DetectFailed",
                "extra_data": {
                    "error": type(exc).__name__,
                },
            },
        )
        return False, 0.0


def _reset_for_tests() -> None:
    """Reset cached singletons + throttle state."""
    global _generator, _detector, _LAST_MISSING_WARN_AT
    _generator = None
    _detector = None
    _LAST_MISSING_WARN_AT = 0.0
