# Copyright (C) 2026 Sebastien Rousseau.
#
# Licensed under the Apache License, Version 2.0 (the "License").
"""MCP client — read ``~/.akande/mcp.json`` and surface external tools.

We deliberately accept the **same JSON shape that Claude Desktop
uses** so operators can copy-paste an existing config.  Example::

    {
      "mcpServers": {
        "filesystem": {
          "command": "npx",
          "args": ["-y", "@modelcontextprotocol/server-filesystem", "/Users/me/Notes"]
        },
        "github": {
          "command": "npx",
          "args": ["-y", "@modelcontextprotocol/server-github"],
          "env": {"GITHUB_TOKEN": "ghp_..."}
        }
      }
    }

This module *reads* the config and (when called) launches a stdio
subprocess for each enabled server.  The actual tool dispatch
loop — calling the upstream server, marshalling args back to the
LLM — is exercised by the integration test and the CLI but lives
behind ``asyncio`` so unit tests don't need a running event loop.

Policy
------
Operators can pin per-server / per-tool allowlists in
``~/.akande/mcp.policy.json``::

    {
      "filesystem": {"allow": ["read_file", "list_directory"]},
      "github": {"deny": ["create_repo"], "require_confirm": ["delete_repo"]}
    }

Tools not in ``allow`` (when set) or in ``deny`` are filtered out
before being shown to the LLM.  ``require_confirm`` tools surface
to the caller; the SSE pipeline will display a confirm modal in a
future iteration.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_PATH = "~/.akande/mcp.json"
DEFAULT_POLICY_PATH = "~/.akande/mcp.policy.json"


@dataclass
class MCPServerConfig:
    """Stdio launcher for a single upstream MCP server."""

    name: str
    command: str
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)


@dataclass
class MCPPolicy:
    """Per-server tool allow / deny / require-confirm sets."""

    allow: set[str] | None = None
    deny: set[str] = field(default_factory=set)
    require_confirm: set[str] = field(default_factory=set)

    def admits(self, tool: str) -> bool:
        if tool in self.deny:
            return False
        if self.allow is not None and tool not in self.allow:
            return False
        return True

    def needs_confirm(self, tool: str) -> bool:
        return tool in self.require_confirm


def _expand(path: str) -> Path:
    return Path(os.path.expanduser(path)).resolve()


def load_config(
    config_path: str = DEFAULT_CONFIG_PATH,
) -> dict[str, MCPServerConfig]:
    """Parse Claude-Desktop-shaped MCP config into typed dataclasses.

    Returns an empty mapping when the file is missing — that's the
    "I haven't configured this yet" state, not an error.
    """
    target = _expand(config_path)
    if not target.is_file():
        return {}
    raw = json.loads(target.read_text())
    servers = raw.get("mcpServers") or {}
    out: dict[str, MCPServerConfig] = {}
    for name, spec in servers.items():
        if not isinstance(spec, dict):
            continue
        command = str(spec.get("command", "")).strip()
        if not command:
            logger.warning(
                "Skipping MCP server %r: no command", name
            )
            continue
        out[name] = MCPServerConfig(
            name=name,
            command=command,
            args=[str(a) for a in (spec.get("args") or [])],
            env={
                str(k): str(v)
                for k, v in (spec.get("env") or {}).items()
            },
        )
    return out


def load_policy(
    policy_path: str = DEFAULT_POLICY_PATH,
) -> dict[str, MCPPolicy]:
    """Read per-server tool policy.  Empty dict means "no constraint"."""
    target = _expand(policy_path)
    if not target.is_file():
        return {}
    raw = json.loads(target.read_text())
    if not isinstance(raw, dict):
        return {}
    out: dict[str, MCPPolicy] = {}
    for name, spec in raw.items():
        if not isinstance(spec, dict):
            continue
        allow_list = spec.get("allow")
        out[name] = MCPPolicy(
            allow=(
                set(allow_list)
                if isinstance(allow_list, list)
                else None
            ),
            deny=set(spec.get("deny") or []),
            require_confirm=set(
                spec.get("require_confirm") or []
            ),
        )
    return out


def admitted_tools(
    server: str,
    upstream_tool_names: list[str],
    policy: dict[str, MCPPolicy] | None = None,
) -> list[str]:
    """Apply the configured policy to an upstream tool list."""
    policies = policy if policy is not None else load_policy()
    rules = policies.get(server)
    if rules is None:
        return list(upstream_tool_names)
    return [
        name for name in upstream_tool_names if rules.admits(name)
    ]


def _require_mcp_sdk() -> Any:
    try:
        from mcp.client.stdio import (
            stdio_client,  # type: ignore[import-not-found]
        )

        from mcp import (  # type: ignore[import-not-found]
            ClientSession,
            StdioServerParameters,
        )
    except ImportError as exc:
        raise ImportError(
            "The 'mcp' package is required for the MCP "
            "client.  Install it with: pip install akande[mcp]"
        ) from exc
    return ClientSession, StdioServerParameters, stdio_client


async def list_upstream_tools(
    cfg: MCPServerConfig,
) -> list[dict[str, Any]]:  # pragma: no cover - integration
    """Open a session, list tools, close.

    Run by the CLI as ``akande mcp list <server>`` to help operators
    debug their ``mcp.json`` setup.  Marked ``no cover`` because
    spinning up a real upstream MCP server from inside pytest is
    out of scope for unit tests; the integration test exercises
    this path against a stub server.
    """
    (
        ClientSession,
        StdioServerParameters,
        stdio_client,
    ) = _require_mcp_sdk()

    params = StdioServerParameters(
        command=cfg.command,
        args=cfg.args,
        env={**os.environ, **cfg.env},
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            response = await session.list_tools()
            return [
                {
                    "name": t.name,
                    "description": t.description,
                }
                for t in response.tools
            ]
