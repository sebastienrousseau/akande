import threading

from akande.logger import MetricsCollector


class TestRecordAndSummary:
    def test_record_and_summary(self):
        mc = MetricsCollector()
        mc.record("llm", 100.0)
        mc.record("llm", 200.0)
        mc.record("llm", 300.0)
        mc.record("tts", 50.0)

        s = mc.summary()
        assert "llm" in s
        assert "tts" in s
        assert s["llm"]["count"] == 3
        assert s["llm"]["mean"] == 200.0
        assert s["llm"]["max"] == 300.0
        assert s["tts"]["count"] == 1
        assert s["tts"]["mean"] == 50.0

    def test_p95_calculation(self):
        mc = MetricsCollector()
        for i in range(1, 101):
            mc.record("stage", float(i))

        s = mc.summary()
        assert s["stage"]["count"] == 100
        assert s["stage"]["p95"] == 95.0
        assert s["stage"]["max"] == 100.0


class TestMetricsThreadSafety:
    def test_metrics_thread_safety(self):
        mc = MetricsCollector()
        num_threads = 10
        per_thread = 100
        barrier = threading.Barrier(num_threads)

        def worker():
            barrier.wait(timeout=5)
            for i in range(per_thread):
                mc.record("stage", float(i))

        threads = [
            threading.Thread(target=worker) for _ in range(num_threads)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        s = mc.summary()
        assert s["stage"]["count"] == (num_threads * per_thread)


class TestResetClearsData:
    def test_reset_clears_data(self):
        mc = MetricsCollector()
        mc.record("llm", 100.0)
        mc.record("tts", 50.0)

        mc.reset()
        s = mc.summary()
        assert s == {}
