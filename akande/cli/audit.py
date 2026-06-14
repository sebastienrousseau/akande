# Copyright (C) 2026 Sebastien Rousseau.
#
# Licensed under the Apache License, Version 2.0 (the "License").
"""``akande verify-audit <path>`` / ``verify-pdf <path>``.

Verifies the Ed25519 signature on an audit sidecar JSON file
written alongside a signed briefing.  When given a ``.pdf`` path,
the matching sidecar at ``<pdf>.audit.json`` is read instead.
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
