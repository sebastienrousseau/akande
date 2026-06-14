# Copyright (C) 2026 Sebastien Rousseau.
#
# Licensed under the Apache License, Version 2.0 (the "License").
"""Eighth coverage boost — last remaining big modules."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

# ============================================================
# google_provider — native streaming
# ============================================================


class TestGoogleProviderStream:
    def test_stream_yields_text(self):
        from akande.providers.google_provider import (
            GoogleProvider,
        )

        p = GoogleProvider.__new__(GoogleProvider)
        p._default_model = "gemini-1.5-flash"
        p._genai = MagicMock()
        gen_model = MagicMock()

        chunks = [
            SimpleNamespace(text="Hello"),
            SimpleNamespace(text=""),
            SimpleNamespace(text=" world"),
        ]
        gen_model.generate_content.return_value = iter(chunks)
        p._genai.GenerativeModel.return_value = gen_model

        async def collect():
            out = []
            async for chunk in p.generate_stream(
                "q", "sys", "gemini-1.5-flash"
            ):
                out.append(chunk)
            return out

        assert asyncio.run(collect()) == ["Hello", " world"]


# ============================================================
# server.rate_limit — Redis backend graceful fallback
# ============================================================


class TestRateLimitRedis:
    def test_build_with_unreachable_redis_falls_back(self):
        from akande.server.rate_limit import (
            InMemoryRateLimiter,
            build_rate_limiter,
        )

        limiter = build_rate_limiter(
            window=60,
            max_requests=10,
            redis_url="redis://nonexistent:9/0",
        )
        # Falls back to in-memory when Redis is unreachable.
        assert isinstance(limiter, InMemoryRateLimiter)


# ============================================================
# memory.py — env var off
# ============================================================


class TestMemoryEnvOff:
    def test_env_off_skips_client(self, monkeypatch):
        from akande.memory import MemoryStore

        monkeypatch.delenv("AKANDE_MEMORY", raising=False)
        ms = MemoryStore()
        assert ms.enabled is False


# ============================================================
# audit — load_or_create returns cached on repeat call
# ============================================================


class TestAuditCacheRepeat:
    def test_load_or_create_cached(self, tmp_path, monkeypatch):
        monkeypatch.setenv("AKANDE_HOME", str(tmp_path))
        from akande.audit import (
            KeyManager,
            _reset_manager_for_tests,
        )

        _reset_manager_for_tests()
        km = KeyManager()
        priv1, pub1 = km.load_or_create()
        # Second call returns same in-memory objects.
        priv2, pub2 = km.load_or_create()
        assert priv1 is priv2
        assert pub1 is pub2


# ============================================================
# skills/finance — _quote network failure paths
# ============================================================


class TestFinanceQuoteFailure:
    def test_url_error_raises_fetch_error(self):
        from urllib.error import URLError

        from akande.skills.finance import (
            FinanceSkill,
            _FetchError,
        )

        s = FinanceSkill()
        with patch(
            "akande.skills.finance.urllib.request.urlopen",
            side_effect=URLError("dns"),
        ):
            with pytest.raises(_FetchError):
                s._quote("AAPL")

    def test_malformed_json_raises_fetch_error(self):
        from akande.skills.finance import (
            FinanceSkill,
            _FetchError,
        )

        s = FinanceSkill()
        resp = MagicMock()
        resp.read.return_value = b"not json"
        resp.__enter__.return_value = resp
        with patch(
            "akande.skills.finance.urllib.request.urlopen",
            return_value=resp,
        ):
            with pytest.raises(_FetchError):
                s._quote("AAPL")


# ============================================================
# tools/web_search — Tavily backend success
# ============================================================


class TestWebSearchTavily:
    def test_tavily_success(self, monkeypatch):
        import json as json_mod

        from akande.tools.web_search import WebSearchTool

        tool = WebSearchTool()
        monkeypatch.delenv("BRAVE_API_KEY", raising=False)
        monkeypatch.setenv("TAVILY_API_KEY", "k")
        payload = {
            "results": [
                {
                    "title": "T",
                    "url": "https://e.com",
                    "content": "snippet",
                }
            ]
        }
        resp = MagicMock()
        resp.read.return_value = json_mod.dumps(payload).encode()
        resp.__enter__.return_value = resp
        with patch(
            "akande.tools.web_search.urllib.request.urlopen",
            return_value=resp,
        ):
            backend, _results = tool._tavily("q", 5), None
        # _tavily returns just the list.
        assert isinstance(backend, list)
        assert backend[0]["title"] == "T"


# ============================================================
# server.py — sse_briefing branch when memory hits is empty
# ============================================================


class TestSSEBriefingNoMemory:
    def test_no_memory_hits(self, tmp_path):
        from akande.conversation import ConversationStore
        from akande.db import ConversationDB
        from akande.server.server import AkandeServer

        db = ConversationDB(str(tmp_path / "x.db"))
        with (
            patch(
                "akande.server.server.validate_api_key",
                return_value=True,
            ),
            patch("akande.server.server.OpenAIImpl"),
        ):
            srv = AkandeServer()
        srv.conversations = ConversationStore(db=db)
        srv.openai_service = MagicMock()
        srv.openai_service.provider_name = "openai"

        async def fake_stream(*args, **kwargs):
            yield "ok"

        srv.openai_service.generate_stream_messages = fake_stream
        # Memory store recall returns empty list.
        srv.memory = MagicMock()
        srv.memory.recall.return_value = []

        conv = srv.conversations.create()
        # Append a user turn so prior_turns is non-empty and
        # exercises the "drop the last user turn" branch.
        srv.conversations.append_turn(
            conv.id, "user", "earlier message"
        )

        events = list(
            srv._sse_briefing(conv.id, "current question", "corr")
        )
        # done event appears at the end.
        text = b"".join(events).decode("utf-8")
        assert "done" in text
