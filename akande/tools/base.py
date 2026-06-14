# Copyright (C) 2026 Sebastien Rousseau.
#
# Licensed under the Apache License, Version 2.0 (the "License").
"""Core types for the Àkàndé tool surface."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


class ToolError(RuntimeError):
    """Raised by a tool when execution fails in a recoverable way.

    The LLM-side function-calling glue surfaces the message verbatim
    back to the model so it can recover or apologise.  Crashes that
    indicate a bug raise the underlying exception unchanged.
    """


@dataclass
class ToolResult:
    """Structured result from a tool invocation.

    ``content`` is the human-readable answer (returned to the LLM
    and ultimately to the user).  ``metadata`` is an arbitrary dict
    for tracing / cost / debugging — never shown to the user.
    """

    content: str
    metadata: dict[str, Any] = field(default_factory=dict)


class Tool(ABC):
    """A callable side-effect or retrieval the LLM can request."""

    #: Stable identifier; used as the function name on the wire.
    name: str = ""
    #: One-line summary shown to the LLM (and to MCP clients).
    description: str = ""

    @property
    @abstractmethod
    def input_schema(self) -> dict[str, Any]:
        """JSON-Schema describing the ``args`` dict for ``run``."""
        ...

    @abstractmethod
    def run(self, args: dict[str, Any]) -> ToolResult:
        """Execute the tool.  Raise :class:`ToolError` on user error."""
        ...

    def to_mcp_dict(self) -> dict[str, Any]:
        """Render as the dict shape ``mcp.types.Tool`` expects."""
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema,
        }


class ToolRegistry:
    """Name → :class:`Tool` instance map with policy hooks.

    The registry is the only thing both the MCP server and the
    upcoming function-calling pipeline talk to, so per-tool
    enable / disable / require-confirm policy lives here.
    """

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}
        self._disabled: set[str] = set()

    def register(self, tool: Tool) -> None:
        if not tool.name:
            raise ValueError(
                "tool must declare a non-empty name"
            )
        if tool.name in self._tools:
            raise ValueError(
                f"tool {tool.name!r} already registered"
            )
        self._tools[tool.name] = tool

    def disable(self, name: str) -> None:
        self._disabled.add(name)

    def enable(self, name: str) -> None:
        self._disabled.discard(name)

    def names(self) -> list[str]:
        return sorted(
            n for n in self._tools if n not in self._disabled
        )

    def get(self, name: str) -> Tool | None:
        if name in self._disabled:
            return None
        return self._tools.get(name)

    def call(
        self, name: str, args: dict[str, Any]
    ) -> ToolResult:
        """Dispatch by name.  Logs every call for audit purposes."""
        tool = self.get(name)
        if tool is None:
            raise ToolError(
                f"unknown or disabled tool: {name!r}"
            )
        logger.info(
            "Tool invoked",
            extra={
                "event": "Tool:Invoked",
                "extra_data": {"name": name},
            },
        )
        return tool.run(args)

    def all_mcp_dicts(self) -> list[dict[str, Any]]:
        return [
            self._tools[n].to_mcp_dict()
            for n in self.names()
        ]
