# Copyright (C) 2026 Sebastien Rousseau.
#
# Licensed under the Apache License, Version 2.0 (the "License").
"""Tool primitives — the shared shape for built-in tools, MCP-
exposed tools, and skill-provided tools.

The vocabulary is deliberately small:

- :class:`Tool` — an ABC with ``name``, ``description``,
  ``input_schema`` (JSON-Schema dict), and ``run(args) -> result``.
- :class:`ToolRegistry` — name → instance map with built-in tool
  registration on first construction.
- :func:`builtin_tools` — return the set of tools we ship by
  default.

Higher-level concerns (per-tool consent, MCP-server adapters,
LLM-side function-calling glue) live in their own modules so this
core stays dep-free and import-cheap.
"""

from __future__ import annotations

from .base import Tool, ToolError, ToolRegistry, ToolResult
from .fetch_url import FetchURLTool
from .web_search import WebSearchTool

__all__ = [
    "Tool",
    "ToolError",
    "ToolRegistry",
    "ToolResult",
    "FetchURLTool",
    "WebSearchTool",
    "builtin_tools",
    "default_registry",
]


def builtin_tools() -> list[Tool]:
    """Return the canonical set of built-in tools."""
    return [WebSearchTool(), FetchURLTool()]


def default_registry() -> ToolRegistry:
    """Construct a registry pre-populated with the built-ins."""
    reg = ToolRegistry()
    for tool in builtin_tools():
        reg.register(tool)
    return reg
