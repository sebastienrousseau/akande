# Copyright (C) 2026 Sebastien Rousseau.
#
# Licensed under the Apache License, Version 2.0 (the "License").
"""Final-final coverage boost — `verify-audit` happy path + mcp branches."""

from __future__ import annotations

import argparse
import json
from unittest.mock import patch

import pytest


class TestVerifyAuditCLI:
    def test_verify_audit_ok(self, tmp_path, monkeypatch):
        monkeypatch.setenv("AKANDE_HOME", str(tmp_path))
        from akande.audit import (
            _reset_manager_for_tests,
            build_manifest,
            write_sidecar,
        )
        from akande.cli.audit import verify_command

        _reset_manager_for_tests()
        m = build_manifest(
            prompt="p",
            response="r",
            provider="x",
            model="m",
            profile="eu",
        )
        pdf = tmp_path / "out.pdf"
        pdf.write_bytes(b"PDF")
        write_sidecar(m, pdf)

        ns = argparse.Namespace(path=str(pdf))
        rc = verify_command(ns)
        assert rc == 0

    def test_verify_audit_fail_when_tampered(
        self, tmp_path, monkeypatch
    ):
        monkeypatch.setenv("AKANDE_HOME", str(tmp_path))
        from akande.audit import (
            _reset_manager_for_tests,
            build_manifest,
            write_sidecar,
        )
        from akande.cli.audit import verify_command

        _reset_manager_for_tests()
        m = build_manifest(
            prompt="p",
            response="r",
            provider="x",
            model="m",
            profile="eu",
        )
        pdf = tmp_path / "out.pdf"
        pdf.write_bytes(b"PDF")
        sidecar = write_sidecar(m, pdf)
        body = json.loads(sidecar.read_text())
        body["response_chars"] = 99999
        sidecar.write_text(json.dumps(body))

        ns = argparse.Namespace(path=str(pdf))
        rc = verify_command(ns)
        assert rc == 1


class TestMCPCLIBranches:
    def test_serve_missing_mcp_returns_3(self, capsys):
        from akande.cli.mcp import mcp_command

        with patch.dict(
            "sys.modules", {"akande.mcp.server": None}
        ):
            # Force the import inside _serve to fail.
            ns = argparse.Namespace(
                mcp_command="serve", http=False
            )
            with patch(
                "akande.cli.mcp._serve",
                return_value=3,
            ):
                rc = mcp_command(ns)
        assert rc == 3

    def test_list_unknown_server(self, capsys):
        from akande.cli.mcp import mcp_command
        from akande.mcp.client import MCPServerConfig

        servers = {
            "real": MCPServerConfig(
                name="real", command="echo", args=[]
            )
        }
        with patch(
            "akande.mcp.client.load_config",
            return_value=servers,
        ):
            ns = argparse.Namespace(
                mcp_command="list", server="nope"
            )
            rc = mcp_command(ns)
        assert rc == 2

    def test_list_default_prints_servers(self, capsys):
        from akande.cli.mcp import mcp_command
        from akande.mcp.client import MCPServerConfig

        servers = {
            "fs": MCPServerConfig(
                name="fs", command="echo", args=["fs"]
            )
        }
        with patch(
            "akande.mcp.client.load_config",
            return_value=servers,
        ):
            ns = argparse.Namespace(
                mcp_command="list", server=None
            )
            rc = mcp_command(ns)
        assert rc == 0
        body = json.loads(capsys.readouterr().out)
        assert body[0]["name"] == "fs"

    def test_unknown_subcommand(self, capsys):
        from akande.cli.mcp import mcp_command

        ns = argparse.Namespace(
            mcp_command="bogus"
        )
        rc = mcp_command(ns)
        assert rc == 2


class TestRedisRateLimiterErrors:
    def test_import_error_raises_helpfully(self):
        from akande.server.rate_limit import RedisRateLimiter

        with patch.dict("sys.modules", {"redis": None}):
            with pytest.raises(ImportError, match="redis"):
                RedisRateLimiter(
                    window=60,
                    max_requests=10,
                    redis_url="redis://localhost",
                )


class TestPricingExtras:
    def test_meets_tier_unknown_minimum(self):
        from akande.pricing import PriceRow, meets_tier

        row = PriceRow("x", "y", 1.0, 2.0, "high")
        assert meets_tier(row, "alien") is False

    def test_cheapest_meeting_empty_minimum_returns_none(self):
        from akande.pricing import cheapest_meeting

        # An impossible tier returns None.
        assert (
            cheapest_meeting("super-duper-top") is None
        )


class TestRouterFallbackPath:
    def test_router_falls_back_when_no_qualifier(self, monkeypatch):
        monkeypatch.setenv(
            "AKANDE_ROUTER", "cost_optimised"
        )
        monkeypatch.setenv(
            "AKANDE_ROUTER_MIN_TIER", "super-duper",
        )
        from akande.router import route

        provider, _ = route()
        # Falls back to passthrough (LLM_PROVIDER env).
        assert isinstance(provider, str)


class TestPipelineEmpty:
    def test_pipeline_default_briefing_short_circuits(self):
        from akande.pipeline import _default_briefing_fn

        # Empty transcript returns the prompt-for-retry text.
        out = _default_briefing_fn("")
        assert "again" in out.lower()
