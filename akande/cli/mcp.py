# Copyright (C) 2026 Sebastien Rousseau.
#
# Licensed under the Apache License, Version 2.0 (the "License").
"""``akande mcp {serve, list}`` — MCP integration subcommands."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from typing import Any


def mcp_command(ns: argparse.Namespace) -> int:
    if ns.mcp_command == "serve":
        return _serve(ns)
    if ns.mcp_command == "list":
        return _list(ns)
    print(
        "usage: akande mcp {serve,list} …",
        file=sys.stderr,
    )
    return 2


def _serve(ns: argparse.Namespace) -> int:  # pragma: no cover - spawns real mcp server
    try:
        from akande.mcp.server import serve
    except ImportError as exc:
        print(str(exc), file=sys.stderr)
        return 3
    try:
        serve(stdio=not ns.http)
    except KeyboardInterrupt:
        return 0
    return 0


def _list(ns: argparse.Namespace) -> int:
    from akande.mcp.client import (
        admitted_tools,
        load_config,
        load_policy,
    )

    servers = load_config()
    if not servers:
        print(
            "no MCP servers configured "
            "(expected ~/.akande/mcp.json)",
            file=sys.stderr,
        )
        return 1

    if ns.server is None:
        server_rows: list[dict[str, Any]] = [
            {
                "name": s.name,
                "command": s.command,
                "args": s.args,
            }
            for s in servers.values()
        ]
        print(
            json.dumps(
                server_rows, sort_keys=True, indent=2
            )
        )
        return 0

    cfg = servers.get(ns.server)
    if cfg is None:
        print(
            f"unknown MCP server: {ns.server!r}",
            file=sys.stderr,
        )
        return 2

    try:  # pragma: no cover - spawns subprocess for upstream introspection
        from akande.mcp.client import list_upstream_tools
    except ImportError as exc:
        print(str(exc), file=sys.stderr)
        return 3

    try:  # pragma: no cover
        tools = asyncio.run(list_upstream_tools(cfg))
    except Exception as exc:
        print(
            f"failed to list tools: {exc}", file=sys.stderr
        )
        return 4

    upstream_names = [str(t["name"]) for t in tools]  # pragma: no cover
    admitted = set(  # pragma: no cover
        admitted_tools(
            ns.server, upstream_names, load_policy()
        )
    )
    tool_rows: list[dict[str, Any]] = []  # pragma: no cover
    for tool in tools:  # pragma: no cover
        tool_rows.append(
            {
                "name": tool.get("name"),
                "description": tool.get("description"),
                "admitted": str(tool.get("name"))
                in admitted,
            }
        )
    print(json.dumps(tool_rows, sort_keys=True, indent=2))  # pragma: no cover
    return 0  # pragma: no cover
