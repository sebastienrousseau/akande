# Copyright (C) 2026 Sebastien Rousseau.
#
# Licensed under the Apache License, Version 2.0 (the "License").
"""Fourth round of coverage boosters."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

# ============================================================
# mistral_provider streaming + error paths
# ============================================================


class TestMistralStreaming:
    def _make(self):
        from akande.providers.mistral_provider import (
            MistralProvider,
        )

        p = MistralProvider.__new__(MistralProvider)
        p._default_model = "mistral-small-latest"
        p.client = MagicMock()
        return p

    def test_stream_yields_deltas(self):
        p = self._make()

        def _chunk(content):
            return SimpleNamespace(
                data=SimpleNamespace(
                    choices=[
                        SimpleNamespace(
                            delta=SimpleNamespace(
                                content=content
                            )
                        )
                    ]
                )
            )

        p.client.chat.stream.return_value = iter(
            [_chunk("Hi"), _chunk(""), _chunk(" world")]
        )

        async def collect():
            out = []
            async for d in p.generate_stream(
                "q", "sys", "mistral-small-latest"
            ):
                out.append(d)
            return out

        chunks = asyncio.run(collect())
        assert chunks == ["Hi", " world"]

    def test_stream_open_failure(self):
        p = self._make()
        p.client.chat.stream.side_effect = RuntimeError(
            "boom"
        )

        async def call():
            async for _ in p.generate_stream(
                "q", "sys", "mistral-small-latest"
            ):
                pass

        with pytest.raises(RuntimeError):
            asyncio.run(call())

    def test_async_raises_on_error(self):
        p = self._make()
        p.client.chat.complete.side_effect = RuntimeError(
            "down"
        )

        async def call():
            return await p.generate_response(
                "hi", "sys", "mistral-small-latest"
            )

        with pytest.raises(RuntimeError):
            asyncio.run(call())


# ============================================================
# weather skill — extra branches in geocode + render
# ============================================================


class TestWeatherSkillMoreBranches:
    def _make(self):
        from akande.skills.weather import WeatherSkill

        return WeatherSkill()

    def test_match_with_question_mark(self):
        intent = self._make().match("weather in Paris?")
        assert intent is not None

    def test_geocode_no_results_raises(self, monkeypatch):
        from akande.skills.weather import _SkillFetchError

        s = self._make()
        with patch.object(
            s,
            "_geocode",
            side_effect=_SkillFetchError("no match"),
        ):
            from akande.skills.base import Intent, SkillContext

            result = s.handle(
                Intent(
                    name="weather", args={"place": "Atlantis"}
                ),
                SkillContext(),
            )
            assert "Could not look up" in result.content

    def test_render_full_includes_all_fields(self):
        from akande.skills.weather import WeatherSkill

        out = WeatherSkill._render(
            "Paris",
            {
                "temperature_2m": 12,
                "apparent_temperature": 10,
                "relative_humidity_2m": 70,
                "wind_speed_10m": 7,
                "weather_code": 63,
            },
        )
        assert "Paris" in out
        assert "rain" in out
        assert "10" in out
        assert "70" in out
        assert "7" in out


# ============================================================
# anthropic generate_response_sync error path
# ============================================================


class TestAnthropicSyncErrorPath:
    def test_sync_raises_on_error(self):
        from akande.providers.anthropic_provider import (
            AnthropicProvider,
        )

        p = AnthropicProvider.__new__(AnthropicProvider)
        p._default_model = "claude-3-haiku-20240307"
        p.client = MagicMock()
        p.client.messages.create.side_effect = RuntimeError(
            "boom"
        )
        with pytest.raises(RuntimeError):
            p.generate_response_sync(
                "hi", "sys", "claude-3-haiku-20240307"
            )


# ============================================================
# tools.calling — final extracted branches
# ============================================================


class TestToolCallingExtractMore:
    def test_extract_assistant_with_dict_tool_call(self):
        from akande.tools.calling import (
            _extract_assistant_message,
        )

        # Dict already in canonical shape — extractor short-circuits.
        call = {
            "id": "abc",
            "type": "function",
            "function": {"name": "x", "arguments": "{}"},
        }
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
        assert out["tool_calls"][0]["id"] == "abc"

    def test_unknown_tool_in_loop(self):
        from akande.tools.base import ToolRegistry
        from akande.tools.calling import (
            run_tool_calling_loop,
        )

        reg = ToolRegistry()

        # No registered tools at all → loop returns immediately.
        provider = MagicMock()
        out = run_tool_calling_loop(
            provider,
            [{"role": "user", "content": "hi"}],
            "m",
            reg,
        )
        assert out.events == []


# ============================================================
# memory.py — env path branch
# ============================================================


class TestMemoryEnvPath:
    def test_env_set_but_mem0_missing(self, monkeypatch):
        from akande.memory import MemoryStore

        monkeypatch.setenv("AKANDE_MEMORY", "1")
        # mem0 not importable → constructor leaves enabled=False
        with patch(
            "akande.memory._mem0_available",
            return_value=False,
        ):
            ms = MemoryStore()
        assert ms.enabled is False


# ============================================================
# install_local — write_env with already populated .env
# ============================================================


class TestInstallLocalWriteEnv:
    def test_write_env_preserves_extra_keys(self, tmp_path):
        from akande.cli.install_local import _write_env

        target = tmp_path / ".env"
        target.write_text(
            "ALREADY=set\nLLM_PROVIDER=openai\n"
        )
        _write_env(
            target, dry_run=False, model="llama3.1"
        )
        body = target.read_text()
        assert "ALREADY=set" in body
        # The custom LLM_PROVIDER survives.
        assert "LLM_PROVIDER=openai" in body
        # Offline defaults are merged but don't override existing.
        assert "AKANDE_MODE=offline" in body


# ============================================================
# utils — generate_pdf with logo file present
# ============================================================


class TestUtilsLogoPresent:
    def test_generate_pdf_with_logo(
        self, tmp_path, monkeypatch
    ):
        monkeypatch.setenv("AKANDE_HOME", str(tmp_path))
        # The repo ships a 512x512.png that the PDF render embeds.
        # Verify the path that includes it runs without error.
        from akande.utils import generate_pdf

        path = generate_pdf("Q", "## H\nbody text here")
        from pathlib import Path

        assert Path(path).is_file()


# ============================================================
# cli/__init__.py — explicit subcommand handlers
# ============================================================


class TestCLIDispatcherSubcommands:
    def test_data_subcommand_routes(
        self, tmp_path, monkeypatch
    ):
        # Dispatch a real data subcommand with arguments and
        # confirm it returns an int exit code.
        from akande.cli import dispatch_subcommand

        monkeypatch.setenv("AKANDE_HOME", str(tmp_path))
        out_path = tmp_path / "dump.json"
        rc = dispatch_subcommand(
            ["data", "export", "--user", "nonexistent",
             "--output", str(out_path)]
        )
        # Returns 0 even when the user has no conversations.
        assert rc == 0
        assert out_path.is_file()


# ============================================================
# audit — write_sidecar then load + verify happy path
# ============================================================


class TestAuditSidecarFull:
    def test_write_sidecar_returns_path(
        self, tmp_path, monkeypatch
    ):
        monkeypatch.setenv("AKANDE_HOME", str(tmp_path))
        from akande.audit import (
            _reset_manager_for_tests,
            build_manifest,
            verify_sidecar,
            write_sidecar,
        )

        _reset_manager_for_tests()
        m = build_manifest(
            prompt="p",
            response="r",
            provider="x",
            model="m",
            profile="eu",
        )
        pdf_path = tmp_path / "b.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 fake")
        sidecar = write_sidecar(m, pdf_path)
        assert sidecar.is_file()
        assert verify_sidecar(sidecar) is True
