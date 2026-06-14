import asyncio
from unittest.mock import MagicMock, AsyncMock, patch

import pytest

from akande.akande import (
    Akande,
    Colors,
    CLEAR_SCREEN,
    MAX_THREAD_WORKERS,
    CACHE_DB_NAME,
)
from akande.exceptions import LLMError


class TestColors:
    def test_reset_defined(self):
        assert Colors.RESET == "\033[0m"

    def test_red_background_defined(self):
        assert Colors.RED_BACKGROUND == "\033[48;2;179;0;15m"


class TestConstants:
    def test_max_thread_workers(self):
        assert MAX_THREAD_WORKERS == 4

    def test_cache_db_name(self):
        assert CACHE_DB_NAME == "akande_cache.db"

    def test_clear_screen_is_ansi(self):
        assert CLEAR_SCREEN == "\033[2J\033[H"


class TestAkandeInit:
    @patch("akande.akande.SQLiteCache")
    @patch("akande.akande.sr.Recognizer")
    def test_init(self, mock_recognizer, mock_cache):
        mock_service = MagicMock()
        akande = Akande(openai_service=mock_service)
        assert akande.openai_service == mock_service
        assert akande.server is None
        assert akande.server_running is False
        assert not akande._cancel_event.is_set()


class TestHashPrompt:
    @patch("akande.akande.SQLiteCache")
    @patch("akande.akande.sr.Recognizer")
    def test_hash_deterministic(
        self, mock_recognizer, mock_cache
    ):
        mock_service = MagicMock()
        akande = Akande(openai_service=mock_service)
        hash1 = akande.hash_prompt("test")
        hash2 = akande.hash_prompt("test")
        assert hash1 == hash2

    @patch("akande.akande.SQLiteCache")
    @patch("akande.akande.sr.Recognizer")
    def test_hash_different_inputs(
        self, mock_recognizer, mock_cache
    ):
        mock_service = MagicMock()
        akande = Akande(openai_service=mock_service)
        hash1 = akande.hash_prompt("test1")
        hash2 = akande.hash_prompt("test2")
        assert hash1 != hash2


class TestGenerateResponse:
    @patch("akande.akande.SQLiteCache")
    @patch("akande.akande.sr.Recognizer")
    def test_cache_hit(
        self, mock_recognizer, mock_cache_cls
    ):
        mock_cache = MagicMock()
        mock_cache.get.return_value = "cached response"
        mock_cache_cls.return_value = mock_cache

        mock_service = MagicMock()
        akande = Akande(openai_service=mock_service)
        akande.cache = mock_cache

        result = asyncio.run(akande.generate_response("test"))
        assert result == "cached response"
        mock_service.generate_response.assert_not_called()

    @patch("akande.akande.SQLiteCache")
    @patch("akande.akande.sr.Recognizer")
    def test_cache_miss(
        self, mock_recognizer, mock_cache_cls
    ):
        mock_cache = MagicMock()
        mock_cache.get.return_value = None
        mock_cache_cls.return_value = mock_cache

        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(
                message=MagicMock(content="  new response  ")
            )
        ]

        mock_service = MagicMock()
        mock_service.generate_response = AsyncMock(
            return_value=mock_response
        )

        akande = Akande(openai_service=mock_service)
        akande.cache = mock_cache

        result = asyncio.run(akande.generate_response("test"))
        assert result == "new response"
        mock_cache.set.assert_called_once()

    @patch("akande.akande.SQLiteCache")
    @patch("akande.akande.sr.Recognizer")
    def test_api_error_raises_llm_error(
        self, mock_recognizer, mock_cache_cls
    ):
        mock_cache = MagicMock()
        mock_cache.get.return_value = None
        mock_cache_cls.return_value = mock_cache

        mock_service = MagicMock()
        mock_service.generate_response = AsyncMock(
            side_effect=Exception("API down")
        )

        akande = Akande(openai_service=mock_service)
        akande.cache = mock_cache

        with pytest.raises(LLMError) as exc_info:
            asyncio.run(
                akande.generate_response("test")
            )
        assert "error occurred" in exc_info.value.user_message.lower()

    @patch("akande.akande.SQLiteCache")
    @patch("akande.akande.sr.Recognizer")
    def test_unexpected_response_returns_empty(
        self, mock_recognizer, mock_cache_cls
    ):
        mock_cache = MagicMock()
        mock_cache.get.return_value = None
        mock_cache_cls.return_value = mock_cache

        # Return a dict (no .choices attribute)
        mock_service = MagicMock()
        mock_service.generate_response = AsyncMock(
            return_value={"error": "bad"}
        )

        akande = Akande(openai_service=mock_service)
        akande.cache = mock_cache

        result = asyncio.run(akande.generate_response("test"))
        assert result == ""

    @patch("akande.akande.SQLiteCache")
    @patch("akande.akande.sr.Recognizer")
    def test_correlation_id_passed(
        self, mock_recognizer, mock_cache_cls
    ):
        mock_cache = MagicMock()
        mock_cache.get.return_value = "cached"
        mock_cache_cls.return_value = mock_cache

        mock_service = MagicMock()
        akande = Akande(openai_service=mock_service)
        akande.cache = mock_cache

        result = asyncio.run(
            akande.generate_response(
                "test", correlation_id="test-123"
            )
        )
        assert result == "cached"


class TestServerLifecycle:
    @patch("akande.akande.SQLiteCache")
    @patch("akande.akande.sr.Recognizer")
    def test_run_server_sets_running(
        self, mock_recognizer, mock_cache
    ):
        mock_service = MagicMock()
        akande = Akande(openai_service=mock_service)

        with patch("akande.akande.cherrypy"):
            asyncio.run(akande.run_server())
            assert akande.server_running is True
            assert akande.server_thread is not None

    @patch("akande.akande.SQLiteCache")
    @patch("akande.akande.sr.Recognizer")
    def test_run_server_noop_when_running(
        self, mock_recognizer, mock_cache
    ):
        mock_service = MagicMock()
        akande = Akande(openai_service=mock_service)
        akande._server_running.set()

        asyncio.run(akande.run_server())
        assert akande.server_thread is None


class TestTTSFallback:
    # After the v0.0.6 TTS abstraction, speak() routes through
    # ``akande.tts.get_tts_backend()`` → ``GTTSBackend.synthesise``
    # which lazy-imports ``gtts``.  Tests therefore patch the call
    # site directly, not the (now removed) top-level import in
    # akande.akande.
    @patch("akande.akande.SQLiteCache")
    @patch("akande.akande.sr.Recognizer")
    @patch("gtts.gTTS")
    @patch("akande.akande._PYTTSX4_AVAILABLE", True)
    @patch("akande.akande.pyttsx4")
    def test_speak_gtts_fallback_to_pyttsx4(
        self,
        mock_pyttsx4,
        mock_gtts_cls,
        mock_recognizer,
        mock_cache,
    ):
        mock_gtts_cls.side_effect = Exception("no network")
        mock_engine = MagicMock()
        mock_pyttsx4.init.return_value = mock_engine

        mock_service = MagicMock()
        akande = Akande(openai_service=mock_service)

        asyncio.run(akande.speak("hello"))
        mock_engine.say.assert_called_once_with("hello")
        mock_engine.runAndWait.assert_called_once()

    @patch("akande.akande.SQLiteCache")
    @patch("akande.akande.sr.Recognizer")
    @patch("gtts.gTTS")
    @patch("akande.akande._PYTTSX4_AVAILABLE", False)
    def test_speak_all_tts_fail_gracefully(
        self,
        mock_gtts_cls,
        mock_recognizer,
        mock_cache,
    ):
        mock_gtts_cls.side_effect = Exception("no network")
        mock_service = MagicMock()
        akande = Akande(openai_service=mock_service)
        # Should not raise
        asyncio.run(akande.speak("hello"))


class TestCancellation:
    @patch("akande.akande.SQLiteCache")
    @patch("akande.akande.sr.Recognizer")
    def test_cancel_stops_generate_response(
        self, mock_recognizer, mock_cache_cls
    ):
        mock_cache = MagicMock()
        mock_cache.get.return_value = None
        mock_cache_cls.return_value = mock_cache

        mock_service = MagicMock()
        akande = Akande(openai_service=mock_service)
        akande.cache = mock_cache
        akande.cancel_pending()

        with pytest.raises(LLMError, match="cancelled"):
            asyncio.run(
                akande.generate_response("test")
            )

    @patch("akande.akande.SQLiteCache")
    @patch("akande.akande.sr.Recognizer")
    def test_reset_cancel_clears_flag(
        self, mock_recognizer, mock_cache_cls
    ):
        mock_service = MagicMock()
        akande = Akande(openai_service=mock_service)
        akande.cancel_pending()
        assert akande._cancel_event.is_set()
        akande.reset_cancel()
        assert not akande._cancel_event.is_set()


class TestPIIProtection:
    @patch("akande.akande.SQLiteCache")
    @patch("akande.akande.sr.Recognizer")
    def test_cache_hit_logs_hash_not_prompt(
        self, mock_recognizer, mock_cache_cls
    ):
        mock_cache = MagicMock()
        mock_cache.get.return_value = "cached"
        mock_cache_cls.return_value = mock_cache

        mock_service = MagicMock()
        akande = Akande(openai_service=mock_service)
        akande.cache = mock_cache

        with patch("akande.akande.logging") as mock_logging:
            asyncio.run(
                akande.generate_response("my secret prompt")
            )
            log_calls = str(mock_logging.info.call_args_list)
            assert "my secret prompt" not in log_calls
