# Copyright (C) 2026 Sebastien Rousseau.
#
# Licensed under the Apache License, Version 2.0 (the "License").
"""Tests for the akande.mcp server + client integration."""

import json

import pytest

from akande.mcp.client import (
    MCPPolicy,
    MCPServerConfig,
    admitted_tools,
    load_config,
    load_policy,
)


class TestLoadConfig:
    def test_missing_file_returns_empty(self, tmp_path):
        assert load_config(str(tmp_path / "nope.json")) == {}

    def test_parses_claude_desktop_shape(self, tmp_path):
        cfg_path = tmp_path / "mcp.json"
        cfg_path.write_text(
            json.dumps(
                {
                    "mcpServers": {
                        "filesystem": {
                            "command": "npx",
                            "args": [
                                "-y",
                                "@modelcontextprotocol/server-filesystem",
                                "/tmp/notes",
                            ],
                        },
                        "github": {
                            "command": "npx",
                            "args": [],
                            "env": {"GITHUB_TOKEN": "x"},
                        },
                    }
                }
            )
        )
        servers = load_config(str(cfg_path))
        assert set(servers) == {"filesystem", "github"}
        fs = servers["filesystem"]
        assert isinstance(fs, MCPServerConfig)
        assert fs.command == "npx"
        assert (
            "/tmp/notes" in fs.args
        )
        assert servers["github"].env == {"GITHUB_TOKEN": "x"}

    def test_skips_entries_without_command(
        self, tmp_path, caplog
    ):
        cfg_path = tmp_path / "mcp.json"
        cfg_path.write_text(
            json.dumps(
                {
                    "mcpServers": {
                        "broken": {"args": ["x"]},
                        "ok": {"command": "echo"},
                    }
                }
            )
        )
        with caplog.at_level("WARNING"):
            servers = load_config(str(cfg_path))
        assert "broken" not in servers
        assert "ok" in servers


class TestPolicy:
    def test_no_rules_admits_everything(self):
        assert admitted_tools(
            "fs", ["read", "write"], {}
        ) == ["read", "write"]

    def test_allow_filters_in(self):
        rules = {"fs": MCPPolicy(allow={"read"})}
        assert admitted_tools(
            "fs", ["read", "write"], rules
        ) == ["read"]

    def test_deny_filters_out(self):
        rules = {"fs": MCPPolicy(deny={"write"})}
        assert admitted_tools(
            "fs", ["read", "write"], rules
        ) == ["read"]

    def test_deny_overrides_allow(self):
        # If a tool appears in both, deny wins.
        rules = {
            "fs": MCPPolicy(
                allow={"read", "write"}, deny={"write"}
            )
        }
        assert admitted_tools(
            "fs", ["read", "write"], rules
        ) == ["read"]

    def test_needs_confirm(self):
        p = MCPPolicy(require_confirm={"delete"})
        assert p.needs_confirm("delete")
        assert not p.needs_confirm("read")


class TestLoadPolicy:
    def test_missing_file_returns_empty(self, tmp_path):
        assert load_policy(str(tmp_path / "nope.json")) == {}

    def test_parses_full_shape(self, tmp_path):
        policy_path = tmp_path / "policy.json"
        policy_path.write_text(
            json.dumps(
                {
                    "filesystem": {
                        "allow": ["read_file"],
                        "deny": ["delete_file"],
                        "require_confirm": ["write_file"],
                    }
                }
            )
        )
        out = load_policy(str(policy_path))
        rules = out["filesystem"]
        assert rules.allow == {"read_file"}
        assert rules.deny == {"delete_file"}
        assert rules.require_confirm == {"write_file"}


class TestServerBuild:
    def test_build_returns_fastmcp(self):
        # Skip if mcp is missing — covered by the import test below.
        pytest.importorskip("mcp")
        from akande.mcp.server import build_server

        app = build_server()
        # FastMCP exposes a name attribute we set explicitly.
        assert app.name == "akande"

    def test_missing_mcp_raises_helpful(self, monkeypatch):
        # Force the SDK check to "not installed" by patching the
        # helper directly.
        from akande.mcp import server as srv

        def _no_mcp():
            raise ImportError(
                "The 'mcp' package is required ..."
            )

        monkeypatch.setattr(
            srv, "_require_mcp_sdk", _no_mcp
        )
        with pytest.raises(ImportError, match="mcp"):
            srv.build_server()
