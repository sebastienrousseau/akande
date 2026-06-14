# Copyright (C) 2026 Sebastien Rousseau.
#
# Licensed under the Apache License, Version 2.0 (the "License").
"""Tests for the LLM tool-calling loop."""

from types import SimpleNamespace
from typing import Any

from akande.tools.base import (
    Tool,
    ToolRegistry,
    ToolResult,
)
from akande.tools.calling import (
    run_tool_calling_loop,
    tools_payload,
)


class _ConstantTool(Tool):
    name = "echo"
    description = "echo a fixed reply"

    def __init__(self, reply: str = "yes") -> None:
        self._reply = reply

    @property
    def input_schema(self) -> dict[str, Any]:
        return {"type": "object", "properties": {}}

    def run(self, args: dict[str, Any]) -> ToolResult:
        return ToolResult(
            content=self._reply,
            metadata={"got": args},
        )


def _envelope(
    *,
    content: str = "",
    tool_calls: list[dict[str, Any]] | None = None,
) -> SimpleNamespace:
    msg = SimpleNamespace(
        content=content,
        tool_calls=tool_calls or [],
    )
    return SimpleNamespace(choices=[SimpleNamespace(message=msg)])


class _StubProvider:
    """Returns a scripted sequence of responses."""

    def __init__(self, *responses: SimpleNamespace) -> None:
        self._responses = list(responses)
        self.calls: list[dict] = []

    def generate_response_sync(
        self,
        user_prompt: str,
        system_prompt: str,
        model: str,
        params=None,
    ):
        self.calls.append(
            {
                "user_prompt": user_prompt,
                "system_prompt": system_prompt,
                "model": model,
                "params": params,
            }
        )
        return self._responses.pop(0)


class TestToolsPayload:
    def test_empty_registry_returns_empty_list(self):
        reg = ToolRegistry()
        assert tools_payload(reg) == []

    def test_renders_openai_shape(self):
        reg = ToolRegistry()
        reg.register(_ConstantTool())
        payload = tools_payload(reg)
        assert payload[0]["type"] == "function"
        assert payload[0]["function"]["name"] == "echo"
        assert "parameters" in payload[0]["function"]


class TestLoop:
    def _reg(self) -> ToolRegistry:
        reg = ToolRegistry()
        reg.register(_ConstantTool("first-reply"))
        return reg

    def test_no_payload_no_call(self):
        # Empty registry → no provider call at all.
        provider = _StubProvider()
        out = run_tool_calling_loop(
            provider,
            [{"role": "user", "content": "hi"}],
            "m",
            ToolRegistry(),
        )
        assert provider.calls == []
        assert out.messages == [{"role": "user", "content": "hi"}]

    def test_terminates_when_no_tool_calls(self):
        provider = _StubProvider(_envelope(content="just answering"))
        out = run_tool_calling_loop(
            provider,
            [{"role": "user", "content": "hi"}],
            "m",
            self._reg(),
        )
        assert out.stopped_reason == "no_more_tool_calls"
        assert out.iterations == 1
        # The assistant message is appended to the conversation.
        assert out.messages[-1]["role"] == "assistant"
        assert out.messages[-1]["content"] == "just answering"

    def test_dispatches_a_tool_call_then_stops(self):
        tool_call = {
            "id": "call_1",
            "type": "function",
            "function": {
                "name": "echo",
                "arguments": '{"x": 1}',
            },
        }
        provider = _StubProvider(
            _envelope(tool_calls=[tool_call]),
            _envelope(content="done"),
        )
        out = run_tool_calling_loop(
            provider,
            [{"role": "user", "content": "ask"}],
            "m",
            self._reg(),
        )
        assert len(out.events) == 1
        assert out.events[0].name == "echo"
        assert out.events[0].result_content == "first-reply"
        # Messages list now has user + assistant(tool_call) +
        # tool(result) + assistant(final).
        roles = [m["role"] for m in out.messages]
        assert roles == ["user", "assistant", "tool", "assistant"]

    def test_malformed_args_surface_as_error(self):
        tool_call = {
            "id": "call_2",
            "type": "function",
            "function": {
                "name": "echo",
                "arguments": "not-json",
            },
        }
        provider = _StubProvider(
            _envelope(tool_calls=[tool_call]),
            _envelope(content="ack"),
        )
        out = run_tool_calling_loop(
            provider,
            [{"role": "user", "content": "ask"}],
            "m",
            self._reg(),
        )
        assert out.events[0].error is not None
        assert "malformed" in out.events[0].error

    def test_max_iterations_caps(self):
        # Provider keeps returning a tool call forever.
        tool_call = {
            "id": "call_loop",
            "type": "function",
            "function": {
                "name": "echo",
                "arguments": "{}",
            },
        }
        responses = [
            _envelope(tool_calls=[tool_call]) for _ in range(10)
        ]
        provider = _StubProvider(*responses)
        out = run_tool_calling_loop(
            provider,
            [{"role": "user", "content": "hi"}],
            "m",
            self._reg(),
            max_iterations=2,
        )
        assert out.stopped_reason == "max_iterations"
        assert out.iterations == 2
