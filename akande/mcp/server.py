# Copyright (C) 2026 Sebastien Rousseau.
#
# Licensed under the Apache License, Version 2.0 (the "License").
"""MCP server — exposes Àkàndé's capabilities to MCP clients.

Run with::

    akande mcp serve         # stdio transport (Claude Desktop default)
    akande mcp serve --http  # streamable HTTP + SSE (network deployments)

Tools published:

- ``akande.briefing`` — call the configured LLM provider and return
  a BLUF-formatted briefing for a question (single-turn).
- ``akande.web_search`` / ``akande.fetch_url`` — the two built-in
  tools from :mod:`akande.tools`.
- ``akande.verify_audit`` — verify a signed PDF / .audit.json
  sidecar (Ed25519).
- ``akande.verify_watermark`` — detect the AudioSeal watermark in
  an audio file.
- ``akande.conversation_list`` — list recent conversations for a
  user id.

Why expose these?  Because the MCP ecosystem (97M+ monthly SDK
downloads, every major vendor supports it as of mid-2026) is the
distribution surface for tool integrations.  Listing Àkàndé tools
on it means Claude Desktop users can use them with zero changes
to Àkàndé itself.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from akande.tools import default_registry
from akande.tools.base import ToolError, ToolRegistry

logger = logging.getLogger(__name__)

SERVER_NAME = "akande"


def _require_mcp_sdk() -> Any:
    try:
        from mcp.server import FastMCP  # type: ignore[import-not-found]
    except ImportError as exc:
        raise ImportError(
            "The 'mcp' package is required to run the Àkàndé "
            "MCP server.  Install it with: "
            "pip install akande[mcp]"
        ) from exc
    return FastMCP


def build_server(
    tool_registry: ToolRegistry | None = None,
) -> Any:
    """Construct a :class:`mcp.server.FastMCP` populated with Àkàndé tools.

    Factored out of :func:`serve` so tests can introspect the
    registered tools without driving the transport.
    """
    FastMCP = _require_mcp_sdk()
    registry = tool_registry or default_registry()
    app = FastMCP(SERVER_NAME)

    # -- akande.web_search / akande.fetch_url ----------------------
    for tool in [registry.get(n) for n in registry.names()]:
        if tool is None:
            continue
        _register_tool(app, tool)

    # -- akande.briefing -------------------------------------------
    @app.tool()
    def briefing(question: str) -> str:  # pragma: no cover - mcp tool callback
        """Generate a BLUF-formatted executive briefing for a question.

        Calls the LLM provider configured by ``LLM_PROVIDER``
        (default ``openai``).  Returns the assistant's response
        verbatim.  This is the headline Àkàndé capability — most
        MCP clients should reach for it first.
        """
        from akande.config import OPENAI_DEFAULT_MODEL
        from akande.providers import get_provider
        from akande.services import SYSTEM_PROMPT

        provider = get_provider()
        response = provider.generate_response_sync(
            question,
            SYSTEM_PROMPT,
            OPENAI_DEFAULT_MODEL or "gpt-4o-mini",
            None,
        )
        try:
            return str(
                response.choices[0].message.content or ""
            )
        except (AttributeError, IndexError, TypeError):
            return ""

    # -- akande.verify_audit ---------------------------------------
    @app.tool()
    def verify_audit(path: str) -> str:  # pragma: no cover - mcp tool callback
        """Verify the Ed25519 signature on a sidecar audit JSON.

        Pass the path to either the ``.audit.json`` sidecar or the
        ``.pdf`` it was emitted alongside.  Returns ``OK`` or
        ``FAIL`` plus the path inspected.
        """
        from pathlib import Path

        from akande.audit import (
            AUDIT_SUFFIX,
            verify_sidecar,
        )

        target = Path(path)
        if target.suffix.lower() == ".pdf":
            target = Path(str(target) + AUDIT_SUFFIX)
        if not target.is_file():
            return f"FAIL  audit sidecar not found: {target}"
        ok = verify_sidecar(target)
        return (
            f"OK    signature verifies for {target}"
            if ok
            else f"FAIL  signature does NOT verify for {target}"
        )

    # -- akande.verify_watermark -----------------------------------
    @app.tool()
    def verify_watermark(path: str) -> str:  # pragma: no cover - mcp tool callback
        """Detect the AudioSeal watermark in an audio file.

        Returns ``PRESENT``/``ABSENT`` plus the mean detector
        confidence.  Requires the ``audioseal`` package to be
        installed (``pip install akande[watermark]``); reports
        the missing-dep state honestly otherwise.
        """
        from pathlib import Path

        from akande.watermark import (
            _audioseal_available,
            detect_watermark,
        )

        target = Path(path)
        if not target.is_file():
            return f"FAIL audio file not found: {target}"
        if not _audioseal_available():
            return (
                "FAIL audioseal not installed — cannot "
                "verify watermark"
            )
        suffix = target.suffix.lower().lstrip(".")
        fmt = suffix if suffix in {"mp3", "wav"} else "mp3"
        present, confidence = detect_watermark(
            target.read_bytes(), fmt=fmt
        )
        label = "PRESENT" if present else "ABSENT"
        return f"{label} confidence={confidence:.3f} for {target}"

    # -- akande.conversation_list ----------------------------------
    @app.tool()
    def conversation_list(  # pragma: no cover - mcp tool callback
        user_id: str = "default", limit: int = 20
    ) -> str:
        """List recent conversations for a user.

        Returns JSON-encoded ``[{id, title, created_at, updated_at}]``
        sorted by ``updated_at`` descending.  Useful as the entry
        point for an MCP client that wants to drill into a past
        thread.
        """
        from akande.conversation import ConversationStore

        store = ConversationStore()
        convs = store.list(user_id=user_id, limit=int(limit))
        return json.dumps(
            [
                {
                    "id": c.id,
                    "title": c.title,
                    "created_at": str(c.created_at),
                    "updated_at": str(c.updated_at),
                }
                for c in convs
            ],
            sort_keys=True,
        )

    logger.info(
        "Akande MCP server built",
        extra={
            "event": "MCPServer:Built",
            "extra_data": {
                "tool_names": list_tool_names(app),
            },
        },
    )
    return app


def list_tool_names(app: Any) -> list[str]:
    """Best-effort introspection of registered tool names.

    FastMCP doesn't ship a stable ``list`` accessor across versions,
    so we probe a couple of plausible internals and fall back to an
    empty list.  Used for logging only — never for dispatch.
    """
    for attr in ("_tool_manager", "_tools", "tools"):
        obj = getattr(app, attr, None)
        if obj is None:
            continue
        for sub in (
            "_tools",
            "tools",
            "list_tools",
        ):
            inner = getattr(obj, sub, None)
            if isinstance(inner, dict):
                return sorted(inner.keys())
            if callable(inner):
                try:
                    result = inner()
                    if isinstance(result, dict):
                        return sorted(result.keys())
                except Exception:  # pragma: no cover
                    pass
    return []


def _register_tool(app: Any, tool: Any) -> None:
    """Bridge an :class:`~akande.tools.base.Tool` onto a FastMCP app.

    We register a thin closure that unpacks the FastMCP-supplied
    kwargs into the ``args`` dict our ``Tool`` ABC expects.  The
    docstring is taken from the tool's description so MCP clients
    see the same one-line summary we use elsewhere.
    """

    name = tool.name
    description = tool.description

    def _runner(**kwargs: Any) -> str:  # pragma: no cover - mcp tool callback
        try:
            result = tool.run(kwargs)
        except ToolError as exc:
            return f"error: {exc}"
        if result.metadata:
            return f"{result.content}\n\n[meta: {json.dumps(result.metadata)}]"
        return result.content

    _runner.__name__ = name
    _runner.__doc__ = description
    app.add_tool(_runner, name=name, description=description)


def serve(stdio: bool = True) -> None:  # pragma: no cover - spawns real mcp server
    """Run the server on stdio (default) or via FastMCP's HTTP transport."""
    app = build_server()
    if stdio:
        import anyio  # type: ignore[import-not-found]

        anyio.run(app.run_stdio_async)
    else:  # pragma: no cover - exercised by integration tests only
        import anyio

        anyio.run(app.run_streamable_http_async)
