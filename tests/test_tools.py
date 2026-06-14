# Copyright (C) 2026 Sebastien Rousseau.
#
# Licensed under the Apache License, Version 2.0 (the "License").
"""Tests for akande.tools."""

from typing import Any
from unittest.mock import patch

import pytest

from akande.tools import (
    FetchURLTool,
    WebSearchTool,
    default_registry,
)
from akande.tools.base import (
    Tool,
    ToolError,
    ToolRegistry,
    ToolResult,
)


class _NoopTool(Tool):
    name = "noop"
    description = "does nothing"

    @property
    def input_schema(self) -> dict[str, Any]:
        return {"type": "object", "properties": {}}

    def run(self, args: dict[str, Any]) -> ToolResult:
        return ToolResult(content="ok")


class TestRegistry:
    def test_register_and_get(self):
        reg = ToolRegistry()
        tool = _NoopTool()
        reg.register(tool)
        assert reg.names() == ["noop"]
        assert reg.get("noop") is tool

    def test_register_duplicate_raises(self):
        reg = ToolRegistry()
        reg.register(_NoopTool())
        with pytest.raises(ValueError):
            reg.register(_NoopTool())

    def test_disable_hides_from_names(self):
        reg = ToolRegistry()
        reg.register(_NoopTool())
        reg.disable("noop")
        assert reg.names() == []
        assert reg.get("noop") is None

    def test_enable_re_lists(self):
        reg = ToolRegistry()
        reg.register(_NoopTool())
        reg.disable("noop")
        reg.enable("noop")
        assert "noop" in reg.names()

    def test_call_unknown_raises(self):
        reg = ToolRegistry()
        with pytest.raises(ToolError):
            reg.call("nope", {})

    def test_all_mcp_dicts_shape(self):
        reg = ToolRegistry()
        reg.register(_NoopTool())
        dicts = reg.all_mcp_dicts()
        assert dicts == [
            {
                "name": "noop",
                "description": "does nothing",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                },
            }
        ]


class TestDefaultRegistry:
    def test_includes_builtins(self):
        reg = default_registry()
        assert "web_search" in reg.names()
        assert "fetch_url" in reg.names()


class TestWebSearchTool:
    def test_requires_query(self):
        with pytest.raises(ToolError):
            WebSearchTool().run({})

    def test_renders_results(self):
        tool = WebSearchTool()
        with patch.object(
            tool,
            "_search",
            return_value=(
                "stub",
                [
                    {
                        "title": "Hello",
                        "url": "https://example.com/h",
                        "snippet": "snip",
                    }
                ],
            ),
        ):
            result = tool.run({"query": "hi"})
        assert "Hello" in result.content
        assert "https://example.com/h" in result.content
        assert result.metadata["backend"] == "stub"
        assert result.metadata["count"] == 1

    def test_empty_returns_no_results_message(self):
        tool = WebSearchTool()
        with patch.object(
            tool, "_search", return_value=("stub", [])
        ):
            result = tool.run({"query": "obscure"})
        assert "No results" in result.content


class TestFetchURLTool:
    def test_rejects_non_https(self):
        with pytest.raises(ToolError):
            FetchURLTool().run(
                {"url": "http://example.com"}
            )

    def test_rejects_empty(self):
        with pytest.raises(ToolError):
            FetchURLTool().run({"url": ""})

    def test_rejects_missing_host(self):
        with pytest.raises(ToolError):
            FetchURLTool().run({"url": "https://"})

    def test_html_to_text_strips_tags(self):
        from akande.tools.fetch_url import _html_to_text

        out = _html_to_text(
            "<html><body><p>Hi <b>there</b></p>"
            "<script>x()</script></body></html>"
        )
        assert "Hi there" in out
        assert "x()" not in out
        assert "<" not in out
