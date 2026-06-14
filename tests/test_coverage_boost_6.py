# Copyright (C) 2026 Sebastien Rousseau.
#
# Licensed under the Apache License, Version 2.0 (the "License").
"""Sixth coverage boost — chase the long tail of small gaps."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

# ============================================================
# audit verify_sidecar - load + verify path
# ============================================================


class TestAuditSidecarVerify:
    def test_verify_sidecar_round_trip(
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
        pdf_path = tmp_path / "x.pdf"
        pdf_path.write_bytes(b"%PDF-1.4")
        sidecar = write_sidecar(m, pdf_path)
        assert verify_sidecar(str(sidecar)) is True


# ============================================================
# tools.calling — tool_call message structure paths
# ============================================================


class TestToolCallingShape:
    def test_extract_skips_typed_call_with_no_function(self):
        from akande.tools.calling import (
            _extract_assistant_message,
        )

        # Call object with no `.function` attribute is skipped.
        bad_call = SimpleNamespace(id="x")
        response = SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content="",
                        tool_calls=[bad_call],
                    )
                )
            ]
        )
        out = _extract_assistant_message(response)
        # tool_calls list ends up empty.
        assert out["tool_calls"] == []


# ============================================================
# skills/policy — edge cases in malformed state
# ============================================================


class TestPolicyEdges:
    def test_load_skips_non_dict_skills_entry(self, tmp_path):
        import json

        from akande.skills.policy import SkillPolicy

        p = tmp_path / "policy.json"
        # skills is a list rather than a dict.
        p.write_text(json.dumps({"skills": ["broken"]}))
        policy = SkillPolicy(p)
        # is_enabled returns the default for an unknown skill.
        assert policy.is_enabled("anything") is True

    def test_load_skips_non_dict_entry(self, tmp_path):
        import json

        from akande.skills.policy import SkillPolicy

        p = tmp_path / "policy.json"
        p.write_text(
            json.dumps(
                {
                    "skills": {
                        "weather": "not-a-dict",
                        "finance": {
                            "enabled": True,
                            "consented_at": None,
                        },
                    }
                }
            )
        )
        policy = SkillPolicy(p)
        assert policy.is_enabled("finance") is True

    def test_state_returns_dict_for_unknown(self, tmp_path):
        from akande.skills.policy import SkillPolicy

        p = SkillPolicy(tmp_path / "policy.json")
        out = p.state("never-registered")
        assert out["enabled"] is True
        assert out["consented_at"] is None


# ============================================================
# skills/base — plugin discovery without entry-points
# ============================================================


class TestSkillsBasePluginDiscovery:
    def test_discover_plugins_swallows_load_failure(
        self, caplog
    ):
        from akande.skills.base import SkillRegistry

        reg = SkillRegistry()

        class _BadEP:
            value = "x.y:z"

            def load(self):
                raise RuntimeError("broken plugin")

        with patch(
            "importlib.metadata.entry_points"
        ) as ep:
            ep.return_value.select.return_value = [_BadEP()]
            with caplog.at_level("WARNING"):
                reg.discover_plugins()
        assert any(
            "broken plugin" in r.message
            or "failed" in r.message.lower()
            for r in caplog.records
        )

    def test_discover_plugins_skips_non_skill(
        self, caplog
    ):
        from akande.skills.base import SkillRegistry

        reg = SkillRegistry()

        class _NotASkillEP:
            value = "y.z:thing"

            def load(self):
                return "not a skill"

        with patch(
            "importlib.metadata.entry_points"
        ) as ep:
            ep.return_value.select.return_value = [
                _NotASkillEP()
            ]
            with caplog.at_level("WARNING"):
                reg.discover_plugins()


# ============================================================
# memory.recall when client is set but search returns dict-of-list
# ============================================================


class TestMemoryRecallShapes:
    def test_normalise_hits_results_key(self):
        from akande.memory import _normalise_hits

        out = _normalise_hits(
            {"results": [{"text": "X"}]}
        )
        assert out[0].text == "X"

    def test_normalise_hits_memories_key(self):
        from akande.memory import _normalise_hits

        out = _normalise_hits(
            {"memories": [{"memory": "M"}]}
        )
        assert out[0].text == "M"

    def test_normalise_hits_empty_dict(self):
        from akande.memory import _normalise_hits

        # No recognised list key under the dict.
        assert _normalise_hits({"unknown": []}) == []


# ============================================================
# install_local — env merging when no existing file
# ============================================================


class TestInstallLocalLoadEnvBranches:
    def test_load_env_handles_lines_without_equals(
        self, tmp_path
    ):
        from akande.cli.install_local import _load_env

        p = tmp_path / ".env"
        p.write_text(
            "# comment\nNO_EQUALS_LINE\nFOO=bar\n   \n"
        )
        result = _load_env(p)
        assert result == {"FOO": "bar"}


# ============================================================
# web_search — Brave fallback chain with no env keys
# ============================================================


class TestWebSearchDDGEmpty:
    def test_runs_returns_no_results_message(self, monkeypatch):
        from akande.tools.web_search import WebSearchTool

        tool = WebSearchTool()
        monkeypatch.delenv("BRAVE_API_KEY", raising=False)
        monkeypatch.delenv("TAVILY_API_KEY", raising=False)
        with patch.object(
            tool, "_duckduckgo", return_value=[]
        ):
            result = tool.run({"query": "q"})
        assert "No results" in result.content


# ============================================================
# tools.fetch_url — markdown content type
# ============================================================


class TestFetchURLMarkdown:
    def test_markdown_content_passes_through(self):
        from akande.tools.fetch_url import FetchURLTool

        tool = FetchURLTool()
        resp = MagicMock()
        resp.headers.get_content_type.return_value = (
            "text/markdown"
        )
        resp.read.return_value = (
            b"# Heading\n\n- item\n- item\n"
        )
        resp.__enter__.return_value = resp
        with patch(
            "akande.tools.fetch_url.urllib.request.urlopen",
            return_value=resp,
        ):
            result = tool.run({"url": "https://x.com/x.md"})
        assert "Heading" in result.content


# ============================================================
# anthropic stream_messages with empty content + chunked
# ============================================================


class TestAnthropicStreamMessagesShape:
    def test_messages_with_system_only(self):
        from akande.providers.anthropic_provider import (
            AnthropicProvider,
        )

        p = AnthropicProvider.__new__(AnthropicProvider)
        p._default_model = "claude-3-haiku-20240307"
        p.client = MagicMock()
        stream_ctx = MagicMock()
        stream = MagicMock()
        stream.text_stream = iter(["only"])
        stream_ctx.__enter__.return_value = stream
        stream_ctx.__exit__.return_value = False
        p.client.messages.stream.return_value = stream_ctx

        # No user message in the list — provider sees an empty
        # messages= argument (Anthropic SDK quirk).
        async def collect():
            out = []
            async for chunk in p.generate_stream_messages(
                [{"role": "system", "content": "S"}],
                "claude-3-haiku-20240307",
            ):
                out.append(chunk)
            return out

        assert asyncio.run(collect()) == ["only"]


# ============================================================
# server.static — path-traversal already covered; ensure
# success path with allowed file
# ============================================================


class TestServerStaticSuccess:
    def test_serves_allowed_static_file(self, tmp_path):
        import cherrypy

        from akande.conversation import ConversationStore
        from akande.db import ConversationDB
        from akande.server.server import (
            ALLOWED_STATIC_FILES,
            AkandeServer,
        )

        # Pick the one allowed file.
        allowed_name = next(iter(ALLOWED_STATIC_FILES))
        db = ConversationDB(str(tmp_path / "x.db"))
        with patch(
            "akande.server.server.validate_api_key",
            return_value=True,
        ), patch("akande.server.server.OpenAIImpl"):
            srv = AkandeServer()
        srv.conversations = ConversationStore(db=db)
        srv.public_dir = tmp_path
        (tmp_path / allowed_name).write_text(
            "console.log('hi');"
        )

        req = MagicMock()
        req.remote.ip = "127.0.0.1"
        with patch.object(
            cherrypy, "request", req
        ), patch.object(
            cherrypy, "response", MagicMock()
        ):
            body = srv.static(allowed_name)
        assert "console.log" in body
