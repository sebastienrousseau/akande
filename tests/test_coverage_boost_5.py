# Copyright (C) 2026 Sebastien Rousseau.
#
# Licensed under the Apache License, Version 2.0 (the "License").
"""Final coverage push — small targeted tests to clear remaining gaps."""

from __future__ import annotations

import asyncio
import os
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from urllib.error import URLError

import pytest


# ============================================================
# utils._maybe_sign_briefing branches
# ============================================================


class TestMaybeSignBriefing:
    def test_signing_writes_sidecar_when_enabled(
        self, tmp_path, monkeypatch
    ):
        monkeypatch.setenv("AKANDE_HOME", str(tmp_path))
        from akande.audit import _reset_manager_for_tests
        from akande.profiles import EU
        from akande.utils import _maybe_sign_briefing

        _reset_manager_for_tests()
        pdf_path = tmp_path / "out.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 fake")
        with patch(
            "akande.utils.active_profile",
            return_value=EU,
        ):
            _maybe_sign_briefing(
                pdf_path=pdf_path,
                question="Q",
                response="R",
                provider="openai",
                model="m",
                correlation_id="cor",
            )
        sidecar = pdf_path.with_suffix(".pdf.audit.json")
        assert sidecar.exists()

    def test_signing_swallows_errors(self, tmp_path):
        from akande.utils import _maybe_sign_briefing

        # Pass a non-Path for pdf_path so build_manifest/write_sidecar
        # raises internally; the helper must swallow it.
        _maybe_sign_briefing(
            pdf_path=12345,  # bogus
            question="Q",
            response="R",
            provider="x",
            model="m",
            correlation_id=None,
        )


# ============================================================
# audit Manager edge cases
# ============================================================


class TestAuditKeyManagerEdges:
    def test_public_key_returns_object(
        self, tmp_path, monkeypatch
    ):
        monkeypatch.setenv("AKANDE_HOME", str(tmp_path))
        from akande.audit import (
            KeyManager,
            _reset_manager_for_tests,
        )

        _reset_manager_for_tests()
        km = KeyManager()
        pub = km.public_key()
        assert pub is not None


# ============================================================
# memory.py — initialise client via env + mem0 present
# ============================================================


class TestMemoryInitWithMem0:
    def test_init_with_explicit_client_skips_env_load(
        self,
    ):
        from akande.memory import MemoryStore

        client = MagicMock()
        ms = MemoryStore(client=client, user_id="alice")
        assert ms.enabled is True
        assert ms.user_id == "alice"

    def test_init_mem0_import_succeeds_but_construct_fails(
        self, monkeypatch
    ):
        from akande.memory import MemoryStore

        monkeypatch.setenv("AKANDE_MEMORY", "1")
        bad_mem0 = MagicMock()
        bad_mem0.Memory.side_effect = RuntimeError(
            "embedding model failed to load"
        )
        with patch(
            "akande.memory._mem0_available",
            return_value=True,
        ), patch.dict(
            "sys.modules", {"mem0": bad_mem0}
        ):
            ms = MemoryStore()
        # Constructor must not raise — disabled gracefully.
        assert ms.enabled is False


# ============================================================
# tools.calling — content-only assistant response
# ============================================================


class TestToolCallingMisc:
    def test_first_system_returns_empty_when_absent(self):
        from akande.tools.calling import _first_system

        assert _first_system([]) == ""
        assert _first_system(
            [{"role": "user", "content": "x"}]
        ) == ""

    def test_last_user_content_handles_no_user(self):
        from akande.tools.calling import _last_user_content

        # All-assistant message list — empty string fallback.
        assert (
            _last_user_content(
                [{"role": "assistant", "content": "x"}]
            )
            == ""
        )


# ============================================================
# install_local — check_ollama on every platform branch
# ============================================================


class TestInstallLocalPlatformHints:
    def test_linux_install_hint(
        self, capsys, monkeypatch
    ):
        from akande.cli.install_local import (
            _check_ollama_binary,
        )

        with patch(
            "akande.cli.install_local.shutil.which",
            return_value=None,
        ), patch(
            "akande.cli.install_local.platform.system",
            return_value="Linux",
        ):
            ok = _check_ollama_binary(dry_run=False)
        assert ok is False
        err = capsys.readouterr().err
        assert "ollama" in err.lower()

    def test_unknown_platform_install_hint(
        self, capsys
    ):
        from akande.cli.install_local import (
            _check_ollama_binary,
        )

        with patch(
            "akande.cli.install_local.shutil.which",
            return_value=None,
        ), patch(
            "akande.cli.install_local.platform.system",
            return_value="Plan9",
        ):
            ok = _check_ollama_binary(dry_run=False)
        assert ok is False
        err = capsys.readouterr().err
        # The hint links to ollama's official download page for
        # platforms we don't recognise.
        assert "ollama" in err.lower()


# ============================================================
# telemetry init internal branches
# ============================================================


class TestTelemetryEnvBranches:
    def setup_method(self):
        from akande import telemetry

        telemetry._reset_for_tests()

    def test_init_when_otel_not_installed(
        self, monkeypatch
    ):
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
            "akande.telemetry._opentelemetry_available",
            return_value=False,
        ), patch(
            "akande.profiles.active_profile",
            return_value=permissive,
        ):
            ok = telemetry.init(force=True)
        assert ok is False


# ============================================================
# server — get_correlation_id when header missing
# ============================================================


class TestServerHelperExtras:
    def test_get_correlation_id_falls_back_to_uuid(
        self, tmp_path
    ):
        import cherrypy

        from akande.conversation import ConversationStore
        from akande.db import ConversationDB
        from akande.server.server import AkandeServer

        db = ConversationDB(str(tmp_path / "x.db"))
        with patch(
            "akande.server.server.validate_api_key",
            return_value=True,
        ), patch("akande.server.server.OpenAIImpl"):
            srv = AkandeServer()
        srv.conversations = ConversationStore(db=db)

        req = MagicMock()
        req.headers = {}  # no X-Request-Id
        with patch.object(cherrypy, "request", req):
            cid = srv._get_correlation_id()
        # uuid4 string is 36 chars.
        assert len(cid) == 36


# ============================================================
# _openai_compat — sync messages happy path
# ============================================================


class TestOpenAICompatSyncMore:
    def test_sync_generate_response_with_params(self):
        from akande.providers.openai_provider import (
            OpenAIProvider,
        )

        p = OpenAIProvider.__new__(OpenAIProvider)
        p._provider_name = "openai"
        p._default_model = "gpt-4o-mini"
        p.client = MagicMock()
        p.client.chat.completions.create.return_value = (
            SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(
                            content="ok"
                        )
                    )
                ]
            )
        )

        out = p.generate_response_sync(
            "hi",
            "sys",
            "gpt-4o-mini",
            params={"temperature": 0.0},
        )
        assert (
            out.choices[0].message.content == "ok"
        )
        # The params dict was forwarded.
        call = p.client.chat.completions.create.call_args
        assert call.kwargs["temperature"] == 0.0
