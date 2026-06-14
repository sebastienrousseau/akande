# Copyright (C) 2026 Sebastien Rousseau.
#
# Licensed under the Apache License, Version 2.0 (the "License").
"""``akande install-local`` — one-command offline-stack bootstrap.

Idempotently brings up the fully-local Àkàndé configuration
described in the plan: Ollama for the LLM, faster-whisper for
STT, gTTS or Kokoro for TTS, AKANDE_MODE=offline + AKANDE_PROFILE
left to the operator's choice.

The script is deliberately small.  It only does what a human can
verify line-by-line:

1. Check for the ``ollama`` binary.  If missing, print the
   official install command for the host OS — we never silently
   ``curl|sh``.
2. Make sure the chosen Ollama model is pulled.  ``ollama pull``
   is idempotent, so re-running this is safe.
3. Pip-install the local STT/TTS extras so the offline mode has
   working backends.
4. Write or update ``.env`` with the offline-friendly defaults,
   preserving any existing values the operator already set.

Exit codes
----------
0 on success / no-op, 1 on user-actionable failure (missing
binary, refused install, etc.), 2 on internal error.
"""

from __future__ import annotations

import argparse
import logging
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict

logger = logging.getLogger(__name__)

DEFAULT_LLM_MODEL = "llama3.1"
DEFAULT_STT = "faster_whisper"
DEFAULT_TTS = "gtts"  # Kokoro is on the operator if they want it.


OFFLINE_ENV_DEFAULTS: Dict[str, str] = {
    "AKANDE_MODE": "offline",
    "LLM_PROVIDER": "ollama",
    "OLLAMA_HOST": "http://localhost:11434",
    "OPENAI_DEFAULT_MODEL": DEFAULT_LLM_MODEL,
    "AKANDE_STT": DEFAULT_STT,
    "AKANDE_TTS": DEFAULT_TTS,
}


def install_local_command(
    ns: argparse.Namespace,
) -> int:
    if not _check_ollama_binary(ns.dry_run):
        return 1
    if not _ensure_model(ns.model, ns.dry_run):
        return 1
    if not _install_extras(ns.dry_run):
        return 1
    target = Path(ns.env_path)
    _write_env(target, ns.dry_run, ns.model)
    print(
        "✓ local stack ready.  Run `akande` (or `akande --classic`) "
        "to use it.",
    )
    return 0


# -- internals ---------------------------------------------------


def _check_ollama_binary(dry_run: bool) -> bool:
    if shutil.which("ollama"):
        print("✓ ollama binary found")
        return True
    sys_name = platform.system().lower()
    if sys_name == "darwin":
        hint = "brew install ollama"
    elif sys_name == "linux":
        hint = "curl -fsSL https://ollama.com/install.sh | sh"
    else:
        hint = "see https://ollama.com/download"
    print(
        "✗ ollama is not installed.\n"
        f"  Install it with:  {hint}\n"
        "  Re-run `akande install-local` once that's done.",
        file=sys.stderr,
    )
    return False


def _ensure_model(model: str, dry_run: bool) -> bool:
    cmd = ["ollama", "pull", model]
    if dry_run:
        print(f"DRY-RUN would run: {' '.join(cmd)}")
        return True
    print(f"→ pulling {model} via ollama (idempotent)")
    try:
        result = subprocess.run(  # nosec B603 - hard-coded binary
            cmd,
            check=False,
            capture_output=True,
            text=True,
            timeout=600,
        )
    except FileNotFoundError:  # pragma: no cover - subprocess race
        print(
            "✗ `ollama` vanished between checks", file=sys.stderr
        )
        return False
    if result.returncode != 0:
        sys.stderr.write(result.stderr)
        return False
    return True


def _install_extras(dry_run: bool) -> bool:
    # Install the runtime extras the offline mode needs.  We keep
    # the list explicit so an operator can audit it; in particular
    # we *don't* install audioseal / kokoro by default because they
    # pull torch.
    extras = "faster-whisper"
    cmd = [
        sys.executable,
        "-m",
        "pip",
        "install",
        "--quiet",
        extras,
    ]
    if dry_run:
        print(f"DRY-RUN would run: {' '.join(cmd)}")
        return True
    print(f"→ pip-installing {extras}")
    try:
        result = subprocess.run(  # nosec B603 - python -m pip
            cmd,
            check=False,
            capture_output=True,
            text=True,
            timeout=600,
        )
    except FileNotFoundError:  # pragma: no cover - subprocess race
        print(
            "✗ python interpreter not found",
            file=sys.stderr,
        )
        return False
    if result.returncode != 0:
        sys.stderr.write(result.stderr)
        return False
    return True


def _write_env(
    target: Path, dry_run: bool, model: str
) -> None:
    defaults = dict(OFFLINE_ENV_DEFAULTS)
    defaults["OPENAI_DEFAULT_MODEL"] = model
    existing = _load_env(target)
    merged = {**defaults, **existing}
    if dry_run:
        print(
            f"DRY-RUN would write {target} with keys "
            f"{sorted(merged)}"
        )
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Generated by `akande install-local`.  Edit freely.",
        "",
    ]
    for key in sorted(merged):
        lines.append(f"{key}={merged[key]}")
    target.write_text("\n".join(lines) + "\n")
    try:
        os.chmod(target, 0o600)
    except OSError:  # pragma: no cover - filesystem-specific
        pass
    print(f"✓ wrote {target}")


def _load_env(path: Path) -> Dict[str, str]:
    if not path.is_file():
        return {}
    out: Dict[str, str] = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        out[key.strip()] = value.strip()
    return out
