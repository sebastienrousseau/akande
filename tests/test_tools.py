# Copyright (C) 2026 Sebastien Rousseau.
#
# Licensed under the Apache License, Version 2.0 (the "License").
"""Tests for akande.tools."""

import urllib.request
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

    def test_register_empty_name_raises(self):
        class _EmptyTool(Tool):
            name = ""
            description = ""

            @property
            def input_schema(self) -> dict[str, Any]:
                return {}

            def run(self, args: dict[str, Any]) -> ToolResult:
                return ToolResult(content="")

        reg = ToolRegistry()
        with pytest.raises(ValueError, match="non-empty name"):
            reg.register(_EmptyTool())

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
        with patch.object(tool, "_search", return_value=("stub", [])):
            result = tool.run({"query": "obscure"})
        assert "No results" in result.content


class TestFetchURLTool:
    def test_rejects_non_https(self):
        with pytest.raises(ToolError):
            FetchURLTool().run({"url": "http://example.com"})

    def test_rejects_empty(self):
        with pytest.raises(ToolError):
            FetchURLTool().run({"url": ""})

    def test_rejects_missing_host(self):
        with pytest.raises(ToolError):
            FetchURLTool().run({"url": "https://"})

    def test_rejects_private_and_loopback_hosts(self):
        tool = FetchURLTool()
        blocked_urls = [
            "https://127.0.0.1/admin",
            "https://169.254.169.254/latest/meta-data",
            "https://10.0.0.1/internal",
            "https://192.168.1.1/router",
            "https://172.16.0.1/dashboard",
            "https://[::1]/secret",
            "https://localhost/api",
            "https://service.internal/data",
            "https://device.local/status",
        ]
        for url in blocked_urls:
            with pytest.raises(
                ToolError, match="restricted destination address"
            ):
                tool.run({"url": url})

    def test_rejects_hostname_resolving_to_private_ip(
        self, monkeypatch
    ):
        import socket

        tool = FetchURLTool()

        fake_addrinfo = [
            (
                socket.AF_INET,
                socket.SOCK_STREAM,
                6,
                "",
                ("10.20.30.40", 443),
            )
        ]
        monkeypatch.setattr(
            socket, "getaddrinfo", lambda *a, **kw: fake_addrinfo
        )
        with pytest.raises(
            ToolError, match="restricted destination address"
        ):
            tool.run({"url": "https://evil-resolved-domain.com/secret"})

    def test_ignores_gaierror_on_unresolvable_host(self, monkeypatch):
        import socket

        def raise_gai(*a, **kw):
            raise socket.gaierror("lookup failed")

        monkeypatch.setattr(socket, "getaddrinfo", raise_gai)
        # Should not raise ToolError from DNS lookup; will fail at urllib level
        from akande.tools.fetch_url import _validate_safe_host

        _validate_safe_host("unresolvable-domain.example", 443)

    def test_html_to_text_strips_tags(self):
        from akande.tools.fetch_url import _html_to_text

        out = _html_to_text(
            "<html><body><p>Hi <b>there</b></p>"
            "<script type='text/javascript'>x()</script >"
            "<style >body { color: red; }</style >"
            "</body></html>"
        )
        assert "Hi there" in out
        assert "x()" not in out
        assert "color: red" not in out
        assert "<" not in out

    def test_input_schema_returns_dict(self):
        tool = FetchURLTool()
        schema = tool.input_schema
        assert schema["type"] == "object"
        assert "url" in schema["properties"]

    def test_validate_safe_host_public_ip_literal(self):
        from akande.tools.fetch_url import _validate_safe_host

        # 8.8.8.8 is a public IP literal, should return cleanly
        _validate_safe_host("8.8.8.8", 443)

    def test_unmocked_open_func_uses_opener(self):
        from unittest.mock import MagicMock

        tool = FetchURLTool()
        mock_opener = MagicMock()
        mock_resp = MagicMock()
        mock_resp.headers.get_content_type.return_value = "text/plain"
        mock_resp.read.return_value = b"public content"
        mock_resp.__enter__.return_value = mock_resp
        mock_opener.open.return_value = mock_resp
        with patch(
            "akande.tools.fetch_url.urllib.request.build_opener",
            return_value=mock_opener,
        ):
            res = tool.run({"url": "https://8.8.8.8"})
            assert res.content == "public content"


class TestSafeRedirectHandler:
    def test_redirect_to_non_https_blocked(self):
        from akande.tools.fetch_url import _SafeRedirectHandler

        handler = _SafeRedirectHandler()
        req = urllib.request.Request("https://example.com/start")
        with pytest.raises(ToolError, match="non-https URL blocked"):
            handler.redirect_request(
                req,
                None,
                302,
                "Found",
                {},
                "http://example.com/insecure",
            )

    def test_redirect_missing_host_blocked(self):
        from akande.tools.fetch_url import _SafeRedirectHandler

        handler = _SafeRedirectHandler()
        req = urllib.request.Request("https://example.com/start")
        with pytest.raises(ToolError, match="missing a host"):
            handler.redirect_request(
                req, None, 302, "Found", {}, "https://"
            )

    def test_redirect_to_private_ip_blocked(self):
        from akande.tools.fetch_url import _SafeRedirectHandler

        handler = _SafeRedirectHandler()
        req = urllib.request.Request("https://example.com/start")
        with pytest.raises(
            ToolError, match="restricted destination address"
        ):
            handler.redirect_request(
                req, None, 302, "Found", {}, "https://127.0.0.1/admin"
            )

    def test_redirect_to_aws_metadata_blocked(self):
        from akande.tools.fetch_url import _SafeRedirectHandler

        handler = _SafeRedirectHandler()
        req = urllib.request.Request("https://example.com/start")
        with pytest.raises(
            ToolError, match="restricted destination address"
        ):
            handler.redirect_request(
                req,
                None,
                302,
                "Found",
                {},
                "https://169.254.169.254/latest",
            )

    def test_redirect_to_valid_https_allowed(self):
        from akande.tools.fetch_url import _SafeRedirectHandler

        handler = _SafeRedirectHandler()
        req = urllib.request.Request("https://example.com/start")
        new_req = handler.redirect_request(
            req,
            None,
            302,
            "Found",
            {},
            "https://example.org/destination",
        )
        assert new_req is not None
        assert new_req.full_url == "https://example.org/destination"
