# Copyright (C) 2026 Sebastien Rousseau.
#
# Licensed under the Apache License, Version 2.0 (the "License").
"""Subcommand router for the Àkàndé CLI.

Used by ``akande/__main__.py``: if ``argv[1]`` is a known
subcommand, :func:`dispatch_subcommand` handles it and returns an
exit code.  Otherwise the caller falls back to the existing
interactive TUI / classic loop.
"""

from __future__ import annotations

import argparse
import sys
from typing import List, Optional

from .audit import verify_command
from .data import data_command

KNOWN_SUBCOMMANDS = {"data", "verify-audit", "verify-pdf"}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="akande",
        description=(
            "Self-hosted, provider-agnostic voice assistant"
        ),
    )
    sub = parser.add_subparsers(dest="command")

    data_parser = sub.add_parser(
        "data",
        help="GDPR data subject controls (export / delete)",
    )
    data_sub = data_parser.add_subparsers(dest="data_command")

    export = data_sub.add_parser(
        "export",
        help="Dump all conversations + turns for a user as JSON",
    )
    export.add_argument(
        "--user",
        default="default",
        help="Data subject identifier (default: 'default')",
    )
    export.add_argument(
        "--output",
        type=str,
        help="Write JSON here (default: stdout)",
    )

    delete = data_sub.add_parser(
        "delete",
        help="Cascade-delete all data for a user",
    )
    delete.add_argument(
        "--user",
        required=True,
        help="Data subject identifier to delete",
    )
    delete.add_argument(
        "--yes",
        action="store_true",
        help="Skip confirmation prompt",
    )

    for name in ("verify-audit", "verify-pdf"):
        v = sub.add_parser(
            name,
            help=(
                "Verify a signed audit sidecar JSON file "
                "(produced alongside every signed briefing)"
            ),
        )
        v.add_argument(
            "path",
            help="Path to the .audit.json file (or .pdf)",
        )
    return parser


def dispatch_subcommand(
    argv: Optional[List[str]] = None,
) -> Optional[int]:
    """Route ``argv`` to a subcommand handler.

    Returns ``None`` if no recognised subcommand is present (so the
    caller proceeds to the interactive loop).  Returns an integer
    exit code otherwise.
    """
    args_list = list(argv if argv is not None else sys.argv[1:])
    if not args_list or args_list[0] not in KNOWN_SUBCOMMANDS:
        return None
    parser = _build_parser()
    ns = parser.parse_args(args_list)
    if ns.command == "data":
        return data_command(ns)
    if ns.command in {"verify-audit", "verify-pdf"}:
        return verify_command(ns)
    parser.print_help()
    return 2
