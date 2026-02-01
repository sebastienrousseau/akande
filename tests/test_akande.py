import asyncio
from unittest.mock import MagicMock, AsyncMock, patch

from akande.akande import (
    Akande,
    Colors,
    CLEAR_SCREEN,
    MAX_THREAD_WORKERS,
    TTS_RATE,
    CACHE_DB_NAME,
)


class TestColors:
    def test_reset_defined(self):
        assert Colors.RESET == "\033[0m"

    def test_header_defined(self):
        assert Colors.HEADER == "\033[95m"


class TestConstants:
    def test_max_thread_workers(self):
        assert MAX_THREAD_WORKERS == 4

    def test_tts_rate(self):
        assert TTS_RATE == 161

    def test_cache_db_name(self):
        assert CACHE_DB_NAME == "akande_cache.db"

    def test_clear_screen_is_ansi(self):
        assert CLEAR_SCREEN == "\033[2J\033[H"


class TestAkandeInit:
    @patch("akande.akande.pyttsx4")
    @patch("akande.akande.SQLiteCache")
    @patch("akande.akande.sr.Recognizer")
    def test_init(self, mock_recognizer, mock_cache, mock_tts):
        mock_service = MagicMock()
        akande = Akande(openai_service=mock_service)
        assert akande.openai_service == mock_service
        assert akande.server is None
        assert akande.server_running is False


class TestHashPrompt:
    @patch("akande.akande.pyttsx4")
    @patch("akande.akande.SQLiteCache")
    @patch("akande.akande.sr.Recognizer")
    def test_hash_deterministic(
        self, mock_recognizer, mock_cache, mock_tts
    ):
        mock_service = MagicMock()
        akande = Akande(openai_service=mock_service)
        hash1 = akande.hash_prompt("test")
        hash2 = akande.hash_prompt("test")
        assert hash1 == hash2

    @patch("akande.akande.pyttsx4")
    @patch("akande.akande.SQLiteCache")
    @patch("akande.akande.sr.Recognizer")
    def test_hash_different_inputs(
        self, mock_recognizer, mock_cache, mock_tts
    ):
        mock_service = MagicMock()
        akande = Akande(openai_service=mock_service)
        hash1 = akande.hash_prompt("test1")
        hash2 = akande.hash_prompt("test2")
        assert hash1 != hash2


class TestGenerateResponse:
    @patch("akande.akande.pyttsx4")
    @patch("akande.akande.SQLiteCache")
    @patch("akande.akande.sr.Recognizer")
    def test_cache_hit(
        self, mock_recognizer, mock_cache_cls, mock_tts
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

    @patch("akande.akande.pyttsx4")
    @patch("akande.akande.SQLiteCache")
    @patch("akande.akande.sr.Recognizer")
    def test_cache_miss(
        self, mock_recognizer, mock_cache_cls, mock_tts
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

    @patch("akande.akande.pyttsx4")
    @patch("akande.akande.SQLiteCache")
    @patch("akande.akande.sr.Recognizer")
    def test_api_error_returns_empty(
        self, mock_recognizer, mock_cache_cls, mock_tts
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

        result = asyncio.run(akande.generate_response("test"))
        assert result == ""

    @patch("akande.akande.pyttsx4")
    @patch("akande.akande.SQLiteCache")
    @patch("akande.akande.sr.Recognizer")
    def test_unexpected_response_returns_empty(
        self, mock_recognizer, mock_cache_cls, mock_tts
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

    @patch("akande.akande.pyttsx4")
    @patch("akande.akande.SQLiteCache")
    @patch("akande.akande.sr.Recognizer")
    def test_correlation_id_passed(
        self, mock_recognizer, mock_cache_cls, mock_tts
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
    @patch("akande.akande.pyttsx4")
    @patch("akande.akande.SQLiteCache")
    @patch("akande.akande.sr.Recognizer")
    def test_run_server_sets_running(
        self, mock_recognizer, mock_cache, mock_tts
    ):
        mock_service = MagicMock()
        akande = Akande(openai_service=mock_service)

        with patch("akande.akande.cherrypy"):
            asyncio.run(akande.run_server())
            assert akande.server_running is True
            assert akande.server_thread is not None

    @patch("akande.akande.pyttsx4")
    @patch("akande.akande.SQLiteCache")
    @patch("akande.akande.sr.Recognizer")
    def test_run_server_noop_when_running(
        self, mock_recognizer, mock_cache, mock_tts
    ):
        mock_service = MagicMock()
        akande = Akande(openai_service=mock_service)
        akande.server_running = True

        asyncio.run(akande.run_server())
        assert akande.server_thread is None


class TestPIIProtection:
    @patch("akande.akande.pyttsx4")
    @patch("akande.akande.SQLiteCache")
    @patch("akande.akande.sr.Recognizer")
    def test_cache_hit_logs_hash_not_prompt(
        self, mock_recognizer, mock_cache_cls, mock_tts
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
