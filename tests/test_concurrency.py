import asyncio
import threading
from unittest.mock import MagicMock, patch

import pytest

from akande.exceptions import LLMError


class TestCancellationStopsGenerateResponse:
    @patch("akande.akande.SQLiteCache")
    @patch("akande.akande.sr.Recognizer")
    def test_cancellation_stops_generate_response(
        self, mock_recognizer, mock_cache_cls
    ):
        from akande.akande import Akande

        mock_cache = MagicMock()
        mock_cache.get.return_value = None
        mock_cache_cls.return_value = mock_cache

        mock_service = MagicMock()
        akande = Akande(openai_service=mock_service)
        akande.cache = mock_cache

        # Set cancel before calling
        akande.cancel_pending()

        with pytest.raises(LLMError, match="cancelled"):
            asyncio.run(
                akande.generate_response("test")
            )


class TestCacheConcurrentReadWrite:
    @patch("akande.akande.SQLiteCache")
    @patch("akande.akande.sr.Recognizer")
    def test_cache_concurrent_read_write(
        self, mock_recognizer, mock_cache_cls
    ):
        """10 threads doing barrier-synchronised cache
        reads and writes should not corrupt data."""
        import tempfile
        from pathlib import Path

        from akande.cache import SQLiteCache

        with tempfile.TemporaryDirectory() as tmpdir:
            cache = SQLiteCache(
                Path(tmpdir) / "test.db"
            )
            num_threads = 10
            barrier = threading.Barrier(num_threads)
            errors = []

            def worker(i):
                try:
                    barrier.wait(timeout=5)
                    key = f"key_{i}"
                    value = f"value_{i}"
                    cache.set(key, value)
                    result = cache.get(key)
                    if result != value:
                        errors.append(
                            f"Thread {i}: expected "
                            f"{value}, got {result}"
                        )
                except Exception as e:
                    errors.append(
                        f"Thread {i}: {e}"
                    )

            threads = [
                threading.Thread(target=worker, args=(i,))
                for i in range(num_threads)
            ]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=10)

            assert errors == [], f"Errors: {errors}"
            cache.close()


class TestRateLimiterConcurrentAccess:
    def test_rate_limiter_concurrent_access(self):
        from akande.server.server import RateLimiter

        limiter = RateLimiter(
            window=60, max_requests=200
        )
        num_threads = 10
        per_thread = 20
        barrier = threading.Barrier(num_threads)
        results = []
        lock = threading.Lock()

        def worker():
            barrier.wait(timeout=5)
            local = []
            for _ in range(per_thread):
                local.append(
                    limiter.is_allowed("127.0.0.1")
                )
            with lock:
                results.extend(local)

        threads = [
            threading.Thread(target=worker)
            for _ in range(num_threads)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        total = num_threads * per_thread
        assert len(results) == total
        assert sum(results) == total
