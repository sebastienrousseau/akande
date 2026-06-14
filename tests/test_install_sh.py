# Copyright (C) 2026 Sebastien Rousseau.
#
# Licensed under the Apache License, Version 2.0 (the "License").
"""Smoke tests for the install.sh shell installer."""

import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
INSTALL_SH = REPO_ROOT / "install.sh"


def test_file_exists():
    assert INSTALL_SH.is_file()


def test_is_executable():
    assert INSTALL_SH.stat().st_mode & 0o111


def test_shebang_is_posix_sh():
    first = INSTALL_SH.read_text().splitlines()[0]
    assert first == "#!/usr/bin/env sh"


def test_posix_syntax():
    # `sh -n` is a parse-only check.  We pick `/bin/sh` because
    # `env sh` may resolve to a busy bash in the test env.
    sh = shutil.which("sh")
    if sh is None:
        pytest.skip("no /bin/sh available")
    result = subprocess.run(  # nosec B603 - hard-coded sh -n
        [sh, "-n", str(INSTALL_SH)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_documents_curl_install_in_header():
    body = INSTALL_SH.read_text()
    assert "curl -fsSL" in body
    assert "akande.co/install.sh" in body


def test_supports_extras_env():
    body = INSTALL_SH.read_text()
    # AKANDE_EXTRAS support is part of the contract — operators
    # should be able to do `AKANDE_EXTRAS=watermark sh install.sh`.
    assert "AKANDE_EXTRAS" in body
