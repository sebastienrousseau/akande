# Copyright (C) 2026 Sebastien Rousseau.
#
# Licensed under the Apache License, Version 2.0 (the "License").
"""Second round of targeted coverage boosters."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

# ============================================================
# anthropic_provider streaming + edge branches
# ============================================================


class TestAnthropicStreamCoverage:
    def _make(self):
        from akande.providers.anthropic_provider import (
            AnthropicProvider,
        )

        p = AnthropicProvider.__new__(AnthropicProvider)
        p._default_model = "claude-3-haiku-20240307"
        p.client = MagicMock()
        return p

    def test_stream_yields_chunks(self):
        p = self._make()
        stream_ctx = MagicMock()
        stream = MagicMock()
        stream.text_stream = iter(["Hello", ", ", "there"])
        stream_ctx.__enter__.return_value = stream
        stream_ctx.__exit__.return_value = False
        p.client.messages.stream.return_value = stream_ctx

        async def collect():
            out = []
            async for chunk in p.generate_stream(
                "hi",
                "system",
                "claude-3-haiku-20240307",
            ):
                out.append(chunk)
            return out

        chunks = asyncio.run(collect())
        assert chunks == ["Hello", ", ", "there"]

    def test_stream_skips_empty_chunks(self):
        p = self._make()
        stream_ctx = MagicMock()
        stream = MagicMock()
        stream.text_stream = iter(["", "Hi", "", "there", ""])
        stream_ctx.__enter__.return_value = stream
        stream_ctx.__exit__.return_value = False
        p.client.messages.stream.return_value = stream_ctx

        async def collect():
            out = []
            async for chunk in p.generate_stream(
                "hi", "sys", "claude-3-haiku-20240307"
            ):
                out.append(chunk)
            return out

        assert asyncio.run(collect()) == ["Hi", "there"]

    def test_stream_open_failure_propagates(self):
        p = self._make()
        p.client.messages.stream.side_effect = RuntimeError("open fail")

        async def collect():
            async for _ in p.generate_stream(
                "hi", "sys", "claude-3-haiku-20240307"
            ):
                pass

        with pytest.raises(RuntimeError):
            asyncio.run(collect())

    def test_messages_stream_native_path(self):
        p = self._make()
        stream_ctx = MagicMock()
        stream = MagicMock()
        stream.text_stream = iter(["A", "B"])
        stream_ctx.__enter__.return_value = stream
        stream_ctx.__exit__.return_value = False
        p.client.messages.stream.return_value = stream_ctx
        msgs = [
            {"role": "system", "content": "You are X"},
            {"role": "user", "content": "Hi"},
        ]

        async def collect():
            out = []
            async for chunk in p.generate_stream_messages(
                msgs, "claude-3-haiku-20240307"
            ):
                out.append(chunk)
            return out

        assert asyncio.run(collect()) == ["A", "B"]


# ============================================================
# _openai_compat sync streaming
# ============================================================


class TestOpenAICompatExtras:
    def test_sync_generate_response_path(self):
        from akande.providers.openai_provider import (
            OpenAIProvider,
        )

        p = OpenAIProvider.__new__(OpenAIProvider)
        p._provider_name = "openai"
        p._default_model = "gpt-4o-mini"
        p.client = MagicMock()
        p.client.chat.completions.create.return_value = SimpleNamespace(
            choices=[
                SimpleNamespace(message=SimpleNamespace(content="sync"))
            ]
        )
        out = p.generate_response_sync("hi", "", "gpt-4o-mini")
        assert out.choices[0].message.content == "sync"

    def test_sync_raises_on_error(self):
        from akande.providers.openai_provider import (
            OpenAIProvider,
        )

        p = OpenAIProvider.__new__(OpenAIProvider)
        p._provider_name = "openai"
        p._default_model = "gpt-4o-mini"
        p.client = MagicMock()
        p.client.chat.completions.create.side_effect = RuntimeError("x")
        with pytest.raises(RuntimeError):
            p.generate_response_sync("hi", "", "gpt-4o-mini")


# ============================================================
# telemetry init success
# ============================================================


class TestTelemetryInitSuccess:
    def setup_method(self):
        from akande import telemetry

        telemetry._reset_for_tests()

    def test_initialises_when_env_and_profile_allow(self, monkeypatch):
        from akande import telemetry
        from akande.profiles import Profile

        monkeypatch.setenv("AKANDE_TELEMETRY", "1")
        permissive = Profile(
            name="dev",
            ai_disclosure=False,
            audio_watermark=False,
            audit_signing=False,
            cache_redact_pii=False,
            telemetry_opt_in=True,
            refuse_voice_clone_without_consent=True,
            eu_residency_hint=False,
            safety_envelope=False,
        )
        with patch(
            "akande.profiles.active_profile",
            return_value=permissive,
        ):
            ok = telemetry.init(force=True)
        assert ok is True
        assert telemetry.tracer() is not None
        # Span yields a real span object now.
        with telemetry.span("test", attr="x") as sp:
            assert sp is not None
        telemetry.record_metric("akande.test", 1.0, label="x")


# ============================================================
# CLI parser bodies — exercise help text generation
# ============================================================


class TestCLIParserBuild:
    def test_unknown_subcommand_help_path(self, capsys):
        from akande.cli import dispatch_subcommand

        # First arg not in KNOWN_SUBCOMMANDS but also not a help
        # flag → returns None so the interactive loop takes over.
        assert dispatch_subcommand(["totally-bogus"]) is None

    def test_help_prints_and_exits_zero(self, capsys):
        from akande.cli import dispatch_subcommand

        rc = dispatch_subcommand(["--help"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "akande" in out.lower()

    def test_version_prints_and_exits_zero(self, capsys):
        from akande.cli import dispatch_subcommand

        rc = dispatch_subcommand(["--version"])
        assert rc == 0
        # Stdout has the version string (e.g. "0.0.6").
        out = capsys.readouterr().out
        assert "." in out

    def test_version_fallback_when_metadata_fails(
        self, capsys, monkeypatch
    ):
        from akande.cli import dispatch_subcommand

        def _boom(_):
            raise RuntimeError("no metadata")

        with patch(
            "importlib.metadata.version",
            side_effect=_boom,
        ):
            rc = dispatch_subcommand(["--version"])
        assert rc == 0
        assert "unknown" in capsys.readouterr().out.lower()


# ============================================================
# mcp/server.py — tool callbacks
# ============================================================


class TestMCPServerInternals:
    def test_list_tool_names_handles_missing_attrs(self):
        from akande.mcp.server import list_tool_names

        # Object with none of the expected attrs.
        assert list_tool_names(MagicMock(spec=[])) == []

    def test_list_tool_names_returns_dict_keys(self):
        from akande.mcp.server import list_tool_names

        app = MagicMock()
        app._tool_manager._tools = {
            "a": object(),
            "b": object(),
        }
        result = list_tool_names(app)
        assert sorted(result) == ["a", "b"]


# ============================================================
# audit verify edge cases
# ============================================================


class TestAuditEdges:
    def test_verify_sidecar_missing_signature_block(self, tmp_path):
        from akande.audit import verify_sidecar

        path = tmp_path / "x.audit.json"
        path.write_text("{}")
        assert verify_sidecar(path) is False

    def test_verify_sidecar_unsupported_alg(
        self, tmp_path, monkeypatch
    ):
        monkeypatch.setenv("AKANDE_HOME", str(tmp_path))
        from akande.audit import (
            _reset_manager_for_tests,
            build_manifest,
            sign_manifest,
            verify_manifest_dict,
        )

        _reset_manager_for_tests()
        m = build_manifest(
            prompt="p",
            response="r",
            provider="x",
            model="m",
            profile="eu",
        )
        body = sign_manifest(m)
        body["signature"]["alg"] = "hmac-sha256"
        assert verify_manifest_dict(body) is False


# ============================================================
# cache.py extra branches
# ============================================================


class TestCacheExtras:
    def test_get_unknown_returns_none(self, tmp_path):
        from akande.cache import SQLiteCache

        c = SQLiteCache(str(tmp_path / "c.db"))
        try:
            assert c.get("nonexistent") is None
        finally:
            c.close()

    def test_set_then_get_roundtrip(self, tmp_path):
        from akande.cache import SQLiteCache

        c = SQLiteCache(str(tmp_path / "c.db"))
        try:
            c.set("h1", "response-text")
            assert c.get("h1") == "response-text"
        finally:
            c.close()

    def test_eviction_when_over_max_size(self, tmp_path):
        from akande.cache import SQLiteCache

        c = SQLiteCache(str(tmp_path / "c.db"), max_size=2)
        try:
            c.set("a", "1")
            c.set("b", "2")
            c.set("c", "3")  # triggers eviction
            # Two of the three should remain.
            remaining = sum(
                1 for k in ("a", "b", "c") if c.get(k) is not None
            )
            assert remaining <= 2
        finally:
            c.close()


# ============================================================
# memory.py extra branches
# ============================================================


class TestMemoryExtras:
    def test_recall_returns_normalised(self):
        from akande.memory import MemoryStore

        client = MagicMock()
        client.search.return_value = [
            {"text": "fact1"},
            {"memory": "fact2"},
            {"content": "fact3"},
        ]
        ms = MemoryStore(client=client)
        hits = ms.recall("q")
        assert [h.text for h in hits] == [
            "fact1",
            "fact2",
            "fact3",
        ]

    def test_remember_swallows_exception(self):
        from akande.memory import MemoryStore

        client = MagicMock()
        client.add.side_effect = RuntimeError("x")
        ms = MemoryStore(client=client)
        # Must not raise.
        ms.remember("a fact")


# ============================================================
# CLI verify-watermark with missing audioseal
# ============================================================


class TestVerifyWatermarkBranches:
    def test_missing_file_exits_2(self, tmp_path, capsys):
        import argparse

        from akande.cli.audit import verify_watermark_command

        ns = argparse.Namespace(
            path=str(tmp_path / "missing.mp3"),
            threshold=0.5,
        )
        rc = verify_watermark_command(ns)
        assert rc == 2

    def test_audioseal_missing_returns_3(self, tmp_path, capsys):
        import argparse

        from akande.cli.audit import verify_watermark_command

        wav = tmp_path / "x.wav"
        wav.write_bytes(b"RIFF" + b"\x00" * 100)
        ns = argparse.Namespace(path=str(wav), threshold=0.5)
        with patch(
            "akande.watermark._audioseal_available",
            return_value=False,
        ):
            rc = verify_watermark_command(ns)
        assert rc == 3


# ============================================================
# tools.calling extra branches
# ============================================================


class TestToolCallingEdges:
    def test_extract_assistant_no_choices(self):
        from akande.tools.calling import _extract_assistant_message

        assert (
            _extract_assistant_message(SimpleNamespace(choices=[]))
            is None
        )

    def test_extract_assistant_no_message(self):
        from akande.tools.calling import _extract_assistant_message

        assert (
            _extract_assistant_message(
                SimpleNamespace(choices=[SimpleNamespace()])
            )
            is None
        )

    def test_extract_with_typed_tool_calls(self):
        from akande.tools.calling import _extract_assistant_message

        call = SimpleNamespace(
            id="x",
            function=SimpleNamespace(name="echo", arguments="{}"),
        )
        response = SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content="",
                        tool_calls=[call],
                    )
                )
            ]
        )
        out = _extract_assistant_message(response)
        assert out["tool_calls"][0]["function"]["name"] == ("echo")


# ============================================================
# utils.py extra branches
# ============================================================


class TestUtilsMoreBranches:
    def test_generate_pdf_smoke(self, tmp_path, monkeypatch):
        monkeypatch.setenv("AKANDE_HOME", str(tmp_path))
        from akande.utils import generate_pdf

        path = generate_pdf(
            "Q",
            "## Overview\nfact.\n## Solution\n- a\n- b",
        )
        from pathlib import Path

        assert Path(path).is_file()
