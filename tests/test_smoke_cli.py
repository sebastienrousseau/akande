# Copyright (C) 2026 Sebastien Rousseau.
#
# Licensed under the Apache License, Version 2.0 (the "License").
"""Smoke test: every CLI subcommand exits 0 on ``--help``.

This catches the entire class of "I added a subcommand to
``akande/cli/`` but forgot to wire it into the parser" bugs that
would otherwise only show up when an operator tries the command
in the wild.  We don't validate the body of the help text — the
test passes if argparse builds the parser and prints something.

The full fresh-install validation lives in
``scripts/regression.sh``; this test is the pytest-side fast loop.
"""

from __future__ import annotations

import subprocess
import sys

import pytest

SUBCOMMANDS = [
    [],
    ["data"],
    ["data", "export"],
    ["data", "delete"],
    ["verify-audit"],
    ["verify-pdf"],
    ["verify-watermark"],
    ["mcp"],
    ["mcp", "serve"],
    ["mcp", "list"],
    ["skill"],
    ["skill", "list"],
    ["skill", "enable"],
    ["skill", "disable"],
    ["skill", "consent"],
    ["skill", "revoke"],
    ["install-local"],
]


@pytest.mark.parametrize("args", SUBCOMMANDS)
def test_subcommand_help_responds(args: list[str]) -> None:
    cmd = [sys.executable, "-m", "akande", *args, "--help"]
    result = subprocess.run(  # nosec B603 - sys.executable + akande
        cmd,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, (
        f"`{' '.join(cmd)}` exited {result.returncode}\n"
        f"stderr:\n{result.stderr}"
    )
    # Sanity: the help text should at least mention `akande`.
    assert (
        "akande" in result.stdout.lower()
        or "akande" in result.stderr.lower()
    )


def test_entry_point_script_exists() -> None:
    """The console_scripts entry point must be on PATH after install."""
    result = subprocess.run(  # nosec B603 - which is read-only
        ["which", "akande"],
        capture_output=True,
        text=True,
        timeout=5,
    )
    # Either `which` finds it, or we're not in an installed env.
    if result.returncode != 0:
        pytest.skip(
            "akande entry point not on PATH "
            "(not installed in current env)"
        )
    assert result.stdout.strip().endswith("akande")
