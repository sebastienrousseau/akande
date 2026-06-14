# Copyright (C) 2026 Sebastien Rousseau.
#
# Licensed under the Apache License, Version 2.0 (the "License").
"""``akande verify-audit`` / ``verify-pdf`` / ``verify-watermark``.

The first two verify the Ed25519 signature on an audit sidecar
JSON file written alongside a signed briefing.  When given a
``.pdf`` path, the matching sidecar at ``<pdf>.audit.json`` is
read instead.

``verify-watermark`` reads an audio file (MP3 or WAV) and reports
whether the AudioSeal mark is detectable, together with the mean
detector confidence.  Useful both as an operator sanity check
("did I really watermark this?") and as an Article 50 audit trail
("here is the evidence the watermark survives a re-encode").
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from akande.audit import AUDIT_SUFFIX, verify_sidecar


def verify_command(ns: argparse.Namespace) -> int:
    path = Path(ns.path)
    if path.suffix.lower() == ".pdf":
        path = Path(str(path) + AUDIT_SUFFIX)
    if not path.is_file():
        print(
            f"audit sidecar not found: {path}",
            file=sys.stderr,
        )
        return 2
    ok = verify_sidecar(path)
    if ok:
        print(f"OK  signature verifies for {path}")
        return 0
    print(
        f"FAIL signature does NOT verify for {path}",
        file=sys.stderr,
    )
    return 1


def verify_watermark_command(
    ns: argparse.Namespace,
) -> int:
    from akande.watermark import (
        _audioseal_available,
        detect_watermark,
    )

    path = Path(ns.path)
    if not path.is_file():
        print(
            f"audio file not found: {path}",
            file=sys.stderr,
        )
        return 2

    if not _audioseal_available():
        print(
            "audioseal not installed — cannot verify "
            "watermark.  Install with: pip install audioseal",
            file=sys.stderr,
        )
        return 3

    suffix = path.suffix.lower().lstrip(".")
    fmt = suffix if suffix in {"mp3", "wav"} else "mp3"
    data = path.read_bytes()
    present, confidence = detect_watermark(data, fmt=fmt)
    threshold = float(getattr(ns, "threshold", 0.5))
    found = confidence >= threshold

    label = "PRESENT" if found else "ABSENT"
    print(
        f"{label:7s} confidence={confidence:.3f} "
        f"(threshold={threshold}) for {path}"
    )
    return 0 if found else 1
