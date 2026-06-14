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

from .audit import verify_command, verify_watermark_command
from .data import data_command
from .install_local import install_local_command
from .mcp import mcp_command
from .skill import skill_command

KNOWN_SUBCOMMANDS = {
    "data",
    "verify-audit",
    "verify-pdf",
    "verify-watermark",
    "mcp",
    "install-local",
    "skill",
}


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

    skill_parser = sub.add_parser(
        "skill",
        help="Manage skills (list / enable / disable / consent / revoke)",
    )
    skill_sub = skill_parser.add_subparsers(
        dest="skill_command"
    )
    skill_sub.add_parser(
        "list", help="List registered skills"
    )
    for action in ("enable", "disable", "consent", "revoke"):
        ap = skill_sub.add_parser(
            action,
            help=f"{action} a skill by name",
        )
        ap.add_argument("name", help="Skill name")

    install_local = sub.add_parser(
        "install-local",
        help=(
            "Bootstrap the fully-offline Àkàndé stack "
            "(checks Ollama, pulls the LLM model, installs "
            "local STT, writes an offline .env)"
        ),
    )
    install_local.add_argument(
        "--model",
        default="llama3.1",
        help="Ollama LLM model to pull (default llama3.1)",
    )
    install_local.add_argument(
        "--env-path",
        default=".env",
        help="Where to write the merged .env (default ./.env)",
    )
    install_local.add_argument(
        "--dry-run",
        action="store_true",
        help="Print intended actions without executing them",
    )

    mcp_parser = sub.add_parser(
        "mcp",
        help="Model Context Protocol integration (server + client)",
    )
    mcp_sub = mcp_parser.add_subparsers(dest="mcp_command")
    mcp_serve = mcp_sub.add_parser(
        "serve",
        help=(
            "Run Àkàndé as an MCP server (stdio by default; "
            "--http for the streamable HTTP transport)"
        ),
    )
    mcp_serve.add_argument(
        "--http",
        action="store_true",
        help="Use streamable HTTP transport instead of stdio",
    )
    mcp_list = mcp_sub.add_parser(
        "list",
        help=(
            "List configured upstream MCP servers from "
            "~/.akande/mcp.json, or tools from a named server"
        ),
    )
    mcp_list.add_argument(
        "server",
        nargs="?",
        help="Name of the upstream server to introspect",
    )

    vw = sub.add_parser(
        "verify-watermark",
        help=(
            "Detect the AudioSeal watermark in an audio file "
            "(MP3 or WAV)"
        ),
    )
    vw.add_argument(
        "path",
        help="Path to the audio file to inspect",
    )
    vw.add_argument(
        "--threshold",
        type=float,
        default=0.5,
        help=(
            "Confidence threshold for declaring the watermark "
            "present (default 0.5)"
        ),
    )
    return parser


def dispatch_subcommand(
    argv: Optional[List[str]] = None,
) -> Optional[int]:
    """Route ``argv`` to a subcommand handler.

    Returns ``None`` if no recognised subcommand is present (so the
    caller proceeds to the interactive loop).  Returns an integer
    exit code otherwise.

    Special cases:
    - ``akande --help`` / ``akande -h``: print the top-level help
      and exit 0.  Without this, the caller would fall through to
      ``_build_akande()`` which complains about a missing
      ``OPENAI_API_KEY`` — a confusing first-run experience.
    - ``akande --version`` / ``-V``: print the installed package
      version and exit 0.
    """
    args_list = list(argv if argv is not None else sys.argv[1:])
    if args_list and args_list[0] in {"--help", "-h"}:
        _build_parser().print_help()
        return 0
    if args_list and args_list[0] in {"--version", "-V"}:
        try:
            from importlib.metadata import version

            print(version("akande"))
        except Exception:
            print("akande (version unknown)")
        return 0
    if not args_list or args_list[0] not in KNOWN_SUBCOMMANDS:
        return None
    parser = _build_parser()
    ns = parser.parse_args(args_list)
    if ns.command == "data":
        return data_command(ns)
    if ns.command in {"verify-audit", "verify-pdf"}:
        return verify_command(ns)
    if ns.command == "verify-watermark":  # pragma: no cover - exercised via subcommand routing
        return verify_watermark_command(ns)
    if ns.command == "mcp":  # pragma: no cover - tested directly
        return mcp_command(ns)
    if ns.command == "install-local":  # pragma: no cover - tested directly
        return install_local_command(ns)
    if ns.command == "skill":  # pragma: no cover - tested directly
        return skill_command(ns)
    parser.print_help()  # pragma: no cover - argparse rejects unknown earlier
    return 2  # pragma: no cover
