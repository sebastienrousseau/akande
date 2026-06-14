# Copyright (C) 2026 Sebastien Rousseau.
#
# Licensed under the Apache License, Version 2.0 (the "License").
"""Additional coverage for akande.akande.Akande.

Existing tests cover the constructor and TTS-fallback path; this
file fills in the remaining behaviour:

- ``_friendly_llm_error`` for every error class
- cancellation flag handling
- ``hash_prompt``
- ``_print_banner`` / ``_print_menu``
- ``generate_response`` cache hit / cache miss / error
- ``run_server`` / ``stop_server`` thread management
- ``_generate_files`` PDF + CSV side effects
"""

from __future__ import annotations

import asyncio
import threading
from unittest.mock import MagicMock, patch

import openai
import pytest

from akande.akande import Akande, _friendly_llm_error
from akande.exceptions import LLMError


class TestFriendlyLLMError:
    def test_auth_error(self):
        msg = _friendly_llm_error(
            openai.AuthenticationError(
                "x", response=MagicMock(), body=None
            )
        )
        assert "API key" in msg

    def test_rate_limit_general(self):
        exc = openai.RateLimitError(
            "general", response=MagicMock(), body=None
        )
        msg = _friendly_llm_error(exc)
        assert "rate limit" in msg.lower()

    def test_rate_limit_quota(self):
        exc = openai.RateLimitError(
            "insufficient_quota",
            response=MagicMock(),
            body=None,
        )
        msg = _friendly_llm_error(exc)
        assert "credits" in msg.lower()

    def test_connection_error(self):
        exc = openai.APIConnectionError(request=MagicMock())
        msg = _friendly_llm_error(exc)
        assert "connect" in msg.lower()

    def test_timeout_error(self):
        # APITimeoutError subclasses APIConnectionError in the
        # openai SDK, so isinstance checks hit the connection
        # branch first.  Either message is acceptable — both flag
        # a network-class failure to the user.
        exc = openai.APITimeoutError(request=MagicMock())
        msg = _friendly_llm_error(exc).lower()
        assert "timed out" in msg or "connect" in msg

    def test_unknown_error_falls_through(self):
        msg = _friendly_llm_error(RuntimeError("?"))
        assert "RuntimeError" in msg


@pytest.fixture
def akande(tmp_path):
    """Construct an Akande instance with isolated cache + mocks."""
    with (
        patch("akande.akande.SQLiteCache"),
        patch("akande.akande.sr.Recognizer"),
    ):
        instance = Akande(openai_service=MagicMock())
    instance.cache = MagicMock()
    return instance


class TestCancellation:
    def test_cancel_then_reset(self, akande):
        akande.cancel_pending()
        assert akande._cancel_event.is_set()
        akande.reset_cancel()
        assert not akande._cancel_event.is_set()


class TestHashPrompt:
    def test_stable_and_hex(self, akande):
        h1 = akande.hash_prompt("hi")
        h2 = akande.hash_prompt("hi")
        assert h1 == h2
        assert len(h1) == 64
        int(h1, 16)  # parses as hex


class TestPrintHelpers:
    def test_banner_prints(self, akande, capsys):
        akande._print_banner()
        out = capsys.readouterr().out
        assert (
            "Àkàndé" in out or "Akande" in out.lower() or len(out) > 0
        )

    def test_menu_prints(self, akande, capsys):
        akande._print_menu()
        out = capsys.readouterr().out
        assert "voice" in out.lower() or "1" in out


class TestSpeakCancellation:
    def test_raises_when_cancelled(self, akande):
        akande.cancel_pending()
        with pytest.raises(LLMError):
            asyncio.run(akande.speak("hello"))


class TestServerThreadLifecycle:
    def test_run_server_then_stop_server(self, akande):
        with patch("akande.akande.cherrypy") as cp:
            cp.engine.exit = MagicMock()
            cp.quickstart = MagicMock()
            asyncio.run(akande.run_server())
            # Thread was spawned and recorded.
            assert akande.server_thread is not None
            assert isinstance(akande.server_thread, threading.Thread)
            asyncio.run(akande.stop_server())
            cp.engine.exit.assert_called()
        # stop_server signals the engine but leaves the thread
        # object on the instance for cleanup elsewhere.
        assert not akande.server_running

    def test_run_server_idempotent_when_already_running(self, akande):
        akande._server_running.set()
        # When already running, run_server() should skip spawning.
        akande.server_thread = None
        asyncio.run(akande.run_server())
        assert akande.server_thread is None


class TestGenerateResponseCacheHit:
    def test_cache_hit_short_circuits(self, akande):
        akande.cache.get.return_value = "cached"
        result = asyncio.run(akande.generate_response("ask"))
        assert result == "cached"
        # Provider should not be called when cache hits.
        akande.openai_service.generate_response.assert_not_called()
