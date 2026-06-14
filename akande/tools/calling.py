# Copyright (C) 2026 Sebastien Rousseau.
#
# Licensed under the Apache License, Version 2.0 (the "License").
"""LLM tool-calling glue — the loop that lets the model use tools.

OpenAI-style ``tools=[{type:"function", function:{...}}]`` is the
de-facto interchange shape in 2026; every provider in
``akande/providers/`` that we run cost-aware routing against
either speaks it natively (OpenAI-compatible family) or maps it
transparently (Anthropic via the OpenAI SDK adapter).  Other
providers fall back to the no-tool path automatically because
they don't return a ``tool_calls`` field on the message.

This module is intentionally *not* async — we keep the loop sync
so the SSE caller (also sync) can iterate over tool-call events
without bouncing through a second event loop.  Streaming token
output from the *final* assistant message stays the async
``generate_stream_messages`` path; the iterative tool-calling
phase precedes it.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from .base import ToolError, ToolRegistry

logger = logging.getLogger(__name__)

DEFAULT_MAX_ITERATIONS = 4


@dataclass
class ToolCallEvent:
    """Surface-able record of one tool round.

    Carried by :class:`ToolCallingResult` so the SSE pipeline can
    emit one ``tool_call`` event per round for the Web UI to
    render in the conversation transcript.
    """

    name: str
    args: dict[str, Any]
    result_content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass
class ToolCallingResult:
    """Outcome of :func:`run_tool_calling_loop`."""

    messages: list[dict[str, Any]]
    events: list[ToolCallEvent] = field(default_factory=list)
    iterations: int = 0
    stopped_reason: str = "ok"


def tools_payload(
    registry: ToolRegistry,
) -> list[dict[str, Any]]:
    """Render the registry as OpenAI-style ``tools=`` payload."""
    out: list[dict[str, Any]] = []
    for entry in registry.all_mcp_dicts():
        out.append(
            {
                "type": "function",
                "function": {
                    "name": entry["name"],
                    "description": entry["description"],
                    "parameters": entry["inputSchema"],
                },
            }
        )
    return out


def run_tool_calling_loop(
    provider: Any,
    messages: list[dict[str, Any]],
    model: str,
    registry: ToolRegistry,
    *,
    max_iterations: int = DEFAULT_MAX_ITERATIONS,
) -> ToolCallingResult:
    """Drive the tool-call → dispatch → response loop.

    Iterates up to ``max_iterations`` times.  At each step:

    1. Call ``provider.generate_response_sync`` with the current
       messages list **and** the tool definitions.
    2. If the response carries no tool calls, stop and return the
       accumulated messages.  The caller streams the final reply
       via ``generate_stream_messages`` against the same list.
    3. Otherwise, dispatch each requested tool via the registry,
       append the assistant + tool messages, and loop.

    Providers that don't speak tool-calling at all return a normal
    text reply; we treat the absence of ``tool_calls`` as "done"
    so this loop is safe to invoke even when ``tools=`` is
    ignored.
    """
    result = ToolCallingResult(messages=list(messages))
    payload = tools_payload(registry)
    if not payload:
        return result
    for iteration in range(1, max_iterations + 1):
        params = {"tools": payload}
        response = provider.generate_response_sync(
            user_prompt=_last_user_content(result.messages),
            system_prompt=_first_system(result.messages),
            model=model,
            params=params,
        )
        message = _extract_assistant_message(response)
        if message is None:
            result.stopped_reason = "no_message"
            break
        tool_calls = message.get("tool_calls") or []
        result.messages.append(
            {
                "role": "assistant",
                "content": message.get("content") or "",
                **({"tool_calls": tool_calls} if tool_calls else {}),
            }
        )
        if not tool_calls:
            result.stopped_reason = "no_more_tool_calls"
            result.iterations = iteration
            return result
        for call in tool_calls:
            event = _dispatch(call, registry)
            result.events.append(event)
            result.messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.get("id", ""),
                    "name": event.name,
                    "content": (
                        event.error
                        if event.error
                        else event.result_content
                    ),
                }
            )
        result.iterations = iteration
    result.stopped_reason = "max_iterations"
    return result


def _dispatch(
    call: dict[str, Any], registry: ToolRegistry
) -> ToolCallEvent:
    fn = call.get("function") or {}
    name = str(fn.get("name", "")).strip()
    raw_args = fn.get("arguments") or "{}"
    if isinstance(raw_args, str):
        try:
            args = json.loads(raw_args) if raw_args else {}
        except json.JSONDecodeError:
            return ToolCallEvent(
                name=name,
                args={},
                result_content="",
                error=("tool_calling: malformed JSON arguments"),
            )
    else:
        args = dict(raw_args)
    try:
        result = registry.call(name, args)
    except ToolError as exc:
        return ToolCallEvent(
            name=name,
            args=args,
            result_content="",
            error=str(exc),
        )
    return ToolCallEvent(
        name=name,
        args=args,
        result_content=result.content,
        metadata=result.metadata,
    )


def _last_user_content(
    messages: list[dict[str, Any]],
) -> str:
    for msg in reversed(messages):
        if msg.get("role") == "user":
            return str(msg.get("content") or "")
    return ""


def _first_system(
    messages: list[dict[str, Any]],
) -> str:
    for msg in messages:
        if msg.get("role") == "system":
            return str(msg.get("content") or "")
    return ""


def _extract_assistant_message(
    response: Any,
) -> dict[str, Any] | None:
    """Best-effort extraction of an OpenAI-shaped assistant message."""
    try:
        choice = response.choices[0]
    except (AttributeError, IndexError, TypeError):
        return None
    message = getattr(choice, "message", None)
    if message is None:
        return None
    # Native SDK objects expose ``.tool_calls`` as a list of typed
    # call objects; we coerce to dicts so the rest of the module
    # speaks one shape.
    content = getattr(message, "content", None)
    tool_calls_raw = getattr(message, "tool_calls", None) or []
    tool_calls: list[dict[str, Any]] = []
    for tc in tool_calls_raw:
        if isinstance(tc, dict):
            tool_calls.append(tc)
            continue
        fn = getattr(tc, "function", None)
        if fn is None:
            continue
        tool_calls.append(
            {
                "id": getattr(tc, "id", "") or "",
                "type": "function",
                "function": {
                    "name": getattr(fn, "name", "") or "",
                    "arguments": getattr(fn, "arguments", "") or "",
                },
            }
        )
    return {
        "content": content or "",
        "tool_calls": tool_calls,
    }
