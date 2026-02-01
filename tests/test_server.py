import json
import time
from unittest.mock import MagicMock, patch

import pytest

from akande.server.server import (
    AkandeServer,
    ALLOWED_STATIC_FILES,
    MAX_QUESTION_LENGTH,
    MAX_AUDIO_SIZE,
    RATE_LIMIT_WINDOW,
    RATE_LIMIT_MAX_REQUESTS,
    RateLimiter,
    _detect_audio_format,
    _hash_ip,
)


class TestAudioFormatDetection:
    def test_detect_webm(self):
        data = b"\x1a\x45\xdf\xa3" + b"\x00" * 100
        assert _detect_audio_format(data) == "webm"

    def test_detect_mp3_id3(self):
        data = b"ID3" + b"\x00" * 100
        assert _detect_audio_format(data) == "mp3"

    def test_detect_ogg(self):
        data = b"OggS" + b"\x00" * 100
        assert _detect_audio_format(data) == "ogg"

    def test_detect_flac(self):
        data = b"fLaC" + b"\x00" * 100
        assert _detect_audio_format(data) == "flac"

    def test_detect_mp4_at_offset(self):
        data = b"\x00\x00\x00\x20ftyp" + b"\x00" * 100
        assert _detect_audio_format(data) == "mp4"

    def test_detect_unknown(self):
        data = b"\x00\x00\x00\x00\x00" * 20
        assert _detect_audio_format(data) == ""


class TestRateLimiter:
    def test_allows_within_limit(self):
        limiter = RateLimiter(window=60, max_requests=5)
        for _ in range(5):
            assert limiter.is_allowed("127.0.0.1") is True

    def test_blocks_over_limit(self):
        limiter = RateLimiter(window=60, max_requests=3)
        for _ in range(3):
            limiter.is_allowed("127.0.0.1")
        assert limiter.is_allowed("127.0.0.1") is False

    def test_different_ips_independent(self):
        limiter = RateLimiter(window=60, max_requests=1)
        assert limiter.is_allowed("1.1.1.1") is True
        assert limiter.is_allowed("2.2.2.2") is True
        assert limiter.is_allowed("1.1.1.1") is False

    def test_cleanup_removes_stale_entries(self):
        limiter = RateLimiter(window=1, max_requests=10)
        limiter.is_allowed("1.1.1.1")
        limiter.is_allowed("2.2.2.2")
        time.sleep(1.1)
        limiter.cleanup()
        assert "1.1.1.1" not in limiter._requests
        assert "2.2.2.2" not in limiter._requests

    def test_thread_safe(self):
        """Rate limiter should work under concurrent access."""
        import threading

        limiter = RateLimiter(window=60, max_requests=100)
        results = []

        def make_requests():
            for _ in range(50):
                results.append(limiter.is_allowed("127.0.0.1"))

        threads = [
            threading.Thread(target=make_requests)
            for _ in range(4)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should have allowed exactly 100
        assert sum(results) == 100
        assert len(results) == 200


class TestHashIp:
    def test_hashes_ip(self):
        result = _hash_ip("127.0.0.1")
        assert isinstance(result, str)
        assert len(result) == 12

    def test_deterministic(self):
        assert _hash_ip("1.2.3.4") == _hash_ip("1.2.3.4")

    def test_different_ips_different_hashes(self):
        assert _hash_ip("1.2.3.4") != _hash_ip("5.6.7.8")


class TestAkandeServerInit:
    @patch(
        "akande.server.server.LLM_PROVIDER", "openai"
    )
    @patch(
        "akande.server.server.OPENAI_API_KEY",
        "sk-test-1234567890abcdef",
    )
    @patch("akande.server.server.OpenAIImpl")
    def test_init(self, mock_impl):
        server = AkandeServer()
        assert server.openai_service is not None
        assert server.public_dir is not None
        assert server.cache is not None

    @patch(
        "akande.server.server.LLM_PROVIDER", "openai"
    )
    @patch("akande.server.server.OPENAI_API_KEY", None)
    def test_init_fails_without_api_key(self):
        with pytest.raises(
            RuntimeError, match="OPENAI_API_KEY"
        ):
            AkandeServer()


class TestStaticFileServing:
    @patch(
        "akande.server.server.OPENAI_API_KEY",
        "sk-test-1234567890abcdef",
    )
    @patch("akande.server.server.OpenAIImpl")
    def test_forbidden_path(self, mock_impl):
        import cherrypy

        server = AkandeServer()
        with pytest.raises(cherrypy.HTTPError) as exc_info:
            server.static("../../etc/passwd")
        assert exc_info.value.status == 403

    @patch(
        "akande.server.server.OPENAI_API_KEY",
        "sk-test-1234567890abcdef",
    )
    @patch("akande.server.server.OpenAIImpl")
    def test_non_allowed_file(self, mock_impl):
        import cherrypy

        server = AkandeServer()
        with pytest.raises(cherrypy.HTTPError) as exc_info:
            server.static("secret.txt")
        assert exc_info.value.status == 403


class TestHealthEndpoint:
    @patch(
        "akande.server.server.OPENAI_API_KEY",
        "sk-test-1234567890abcdef",
    )
    @patch("akande.server.server.OpenAIImpl")
    @patch("akande.server.server.cherrypy")
    def test_health_returns_ok(self, mock_cp, mock_impl):
        mock_cp.response = MagicMock()
        mock_cp.response.headers = {}
        server = AkandeServer()
        result = server.health()
        data = json.loads(result)
        assert data["status"] == "ok"
        assert data["service"] == "akande"


class TestProcessAudio:
    def test_process_audio_unknown_value(self, tmp_path):
        import wave

        wav_path = tmp_path / "test.wav"
        with wave.open(str(wav_path), "w") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            wf.writeframes(b"\x00" * 32000)

        with patch(
            "akande.server.server.sr.Recognizer"
        ) as mock_recognizer_cls:
            mock_recognizer = MagicMock()
            mock_recognizer_cls.return_value = mock_recognizer

            from speech_recognition import UnknownValueError

            # Patch the module-level _recognizer
            with patch(
                "akande.server.server._recognizer"
            ) as mock_rec:
                mock_rec.recognize_google.side_effect = (
                    UnknownValueError()
                )

                result = AkandeServer.process_audio(
                    str(wav_path)
                )
                assert result["success"] is False
                assert "could not be understood" in result["error"]


class TestConstants:
    def test_allowed_static_files(self):
        assert "sine-wave-generator.js" in ALLOWED_STATIC_FILES

    def test_max_question_length(self):
        assert MAX_QUESTION_LENGTH == 5000

    def test_max_audio_size(self):
        assert MAX_AUDIO_SIZE == 10 * 1024 * 1024

    def test_rate_limit_window(self):
        assert RATE_LIMIT_WINDOW == 60

    def test_rate_limit_max_requests(self):
        assert RATE_LIMIT_MAX_REQUESTS == 20
