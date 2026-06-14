import tempfile
import time
from pathlib import Path

from akande.budgets import (
    CACHE_BUDGET_MS,
    E2E_BUDGET_MS,
    LLM_BUDGET_MS,
    STT_BUDGET_MS,
    TTS_BUDGET_MS,
)


class TestBudgetConstants:
    def test_tts_budget_is_positive(self):
        assert TTS_BUDGET_MS > 0

    def test_stt_budget_is_positive(self):
        assert STT_BUDGET_MS > 0

    def test_llm_budget_is_positive(self):
        assert LLM_BUDGET_MS > 0

    def test_e2e_budget_is_positive(self):
        assert E2E_BUDGET_MS > 0

    def test_cache_budget_is_positive(self):
        assert CACHE_BUDGET_MS > 0

    def test_e2e_exceeds_component_budgets(self):
        assert E2E_BUDGET_MS >= (
            TTS_BUDGET_MS + LLM_BUDGET_MS
        )

    def test_cache_budget_is_smallest(self):
        assert CACHE_BUDGET_MS < TTS_BUDGET_MS
        assert CACHE_BUDGET_MS < STT_BUDGET_MS
        assert CACHE_BUDGET_MS < LLM_BUDGET_MS

    def test_budget_values(self):
        assert TTS_BUDGET_MS == 2000
        assert STT_BUDGET_MS == 3000
        assert LLM_BUDGET_MS == 5000
        assert E2E_BUDGET_MS == 12000
        assert CACHE_BUDGET_MS == 50


class TestCacheLookupWithinBudget:
    def test_cache_lookup_within_budget(self):
        from akande.cache import SQLiteCache

        with tempfile.TemporaryDirectory() as tmpdir:
            cache = SQLiteCache(
                Path(tmpdir) / "test.db"
            )
            cache.set("test_key", "test_value")

            start = time.time()
            result = cache.get("test_key")
            elapsed_ms = (time.time() - start) * 1000

            assert result == "test_value"
            assert elapsed_ms < CACHE_BUDGET_MS, (
                f"Cache lookup took {elapsed_ms:.1f}ms, "
                f"budget is {CACHE_BUDGET_MS}ms"
            )
            cache.close()
