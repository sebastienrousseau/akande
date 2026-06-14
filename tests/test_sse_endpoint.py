# Copyright (C) 2026 Sebastien Rousseau.
#
# Licensed under the Apache License, Version 2.0 (the "License").
"""Tests for the v0.0.6 Track B /api/stream SSE endpoint."""

import json
from unittest.mock import MagicMock, patch

import cherrypy
import pytest


@pytest.fixture
def server(tmp_path):
    """Build an AkandeServer with the conversation DB pinned to tmp."""
    from akande.conversation import ConversationStore
    from akande.db import ConversationDB
    from akande.server.server import AkandeServer

    db = ConversationDB(str(tmp_path / "conversations.db"))

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

    async def fake_stream(*args, **kwargs):
        for chunk in ["Hello", ", ", "world."]:
            yield chunk

    srv.openai_service.generate_stream = fake_stream
    srv.openai_service.generate_stream_messages = fake_stream
    srv.openai_service.provider_name = "openai"
    return srv


def _parse_sse_events(payload):
    """Pull JSON dicts out of an SSE byte stream."""
    text = b"".join(payload).decode("utf-8")
    events = []
    for line in text.split("\n\n"):
        line = line.strip()
        if not line.startswith("data: "):
            continue
        events.append(json.loads(line[len("data: ") :]))
    return events


class TestStreamEndpoint:
    def test_emits_meta_deltas_and_done(self, server):
        conv = server.conversations.create()
        events = _parse_sse_events(
            server._sse_briefing(conv.id, "what is QE?", "corr-xyz")
        )
        kinds = [e["type"] for e in events]
        assert kinds[0] == "meta"
        assert events[0]["conversation_id"] == conv.id
        assert "delta" in kinds
        assert kinds[-1] == "done"
        deltas = [e["content"] for e in events if e["type"] == "delta"]
        assert "".join(deltas) == "Hello, world."

    def test_persists_user_and_assistant_turns(self, server):
        # Pre-create a conversation so we can inspect appended turns.
        conv = server.conversations.create()
        list(
            server._sse_briefing(
                conv.id, "ignored at this level", "corr"
            )
        )
        turns = server.conversations.recent_turns(conv.id)
        # The route appends the user turn; _sse_briefing appends the
        # assistant turn after the stream completes.
        assert any(t.role == "assistant" for t in turns)
        assistant = [t for t in turns if t.role == "assistant"][-1]
        assert assistant.content == "Hello, world."
        assert assistant.provider == "openai"

    def test_error_emits_final_error_event(self, server):
        conv = server.conversations.create()

        async def boom(*args, **kwargs):
            if False:
                yield ""  # pragma: no cover
            raise RuntimeError("provider exploded")

        server.openai_service.generate_stream = boom
        server.openai_service.generate_stream_messages = boom
        events = _parse_sse_events(
            server._sse_briefing(conv.id, "q", "corr")
        )
        assert events[-1]["type"] == "error"
        assert "message" in events[-1]


class TestStreamRoute:
    """Smoke test of the public ``stream()`` route input validation."""

    def _make_request(self, body_bytes, headers=None):
        req = MagicMock()
        req.body.read.return_value = body_bytes
        req.headers = headers or {"X-Requested-With": "AkandeApp"}
        req.remote.ip = "127.0.0.1"
        req.path_info = "/stream"
        return req

    def test_rejects_invalid_json(self, server):
        req = self._make_request(b"not json")
        with (
            patch.object(cherrypy, "request", req),
            patch.object(cherrypy, "response", MagicMock()),
            patch("akande.server.server.AKANDE_API_KEY", None),
        ):
            result = server.stream()
        # 400 path returns bytes containing the JSON error.
        assert b"Invalid JSON" in result

    def test_rejects_empty_question(self, server):
        req = self._make_request(
            json.dumps({"question": "   "}).encode()
        )
        with (
            patch.object(cherrypy, "request", req),
            patch.object(cherrypy, "response", MagicMock()),
            patch("akande.server.server.AKANDE_API_KEY", None),
        ):
            result = server.stream()
        assert b"non-empty string" in result

    def test_rejects_non_string_conversation_id(self, server):
        body = json.dumps(
            {"question": "Hi", "conversation_id": 42}
        ).encode()
        req = self._make_request(body)
        with (
            patch.object(cherrypy, "request", req),
            patch.object(cherrypy, "response", MagicMock()),
            patch("akande.server.server.AKANDE_API_KEY", None),
        ):
            result = server.stream()
        assert b"conversation_id" in result
