# Copyright (C) 2026 Sebastien Rousseau.
#
# Licensed under the Apache License, Version 2.0 (the "License").
"""Tests for the latency budget benchmark."""

import importlib.util
from pathlib import Path

import pytest


RUNNER_PATH = (
    Path(__file__).resolve().parents[1] / "bench" / "latency.py"
)


def _load_runner():
    spec = importlib.util.spec_from_file_location(
        "latency_runner", str(RUNNER_PATH)
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


lat = _load_runner()


class TestPercentile:
    def test_zero_when_empty(self):
        assert lat._percentile([], 50) == 0.0

    def test_p50_is_median(self):
        assert lat._percentile([1.0, 2.0, 3.0], 50) == 2.0

    def test_p95_interpolates(self):
        # P95 of 1..10 is 9.55 with linear interpolation.
        out = lat._percentile(
            [float(i) for i in range(1, 11)], 95
        )
        assert out == pytest.approx(9.55)


class TestSummary:
    def test_includes_count_and_stats(self):
        s = lat._summary("STT", [1.0, 2.0, 3.0])
        assert s["label"] == "STT"
        assert s["count"] == 3
        assert s["p50_ms"] == 2.0
        assert s["mean_ms"] == 2.0

    def test_handles_empty(self):
        s = lat._summary("STT", [])
        assert s["count"] == 0
        assert s["mean_ms"] == 0.0
        assert s["p95_ms"] == 0.0


class TestRunSynthetic:
    def test_records_all_stages(self):
        import argparse

        ns = argparse.Namespace(
            n=3,
            output="/tmp/latency.md",
            real=False,
        )
        stats = lat.run(ns)
        assert set(stats) == {
            "mode",
            "n",
            "stt",
            "llm",
            "tts",
            "e2e",
        }
        assert stats["mode"] == "synthetic"
        assert stats["n"] == 3
        # Each stage has at least one observation.
        for stage in ("stt", "llm", "tts", "e2e"):
            assert stats[stage]["count"] == 3


class TestRender:
    def test_renders_markdown_with_table(self):
        stats = {
            "mode": "synthetic",
            "n": 5,
            "stt": {
                "label": "STT",
                "p50_ms": 10,
                "p95_ms": 20,
                "mean_ms": 15,
            },
            "llm": {
                "label": "LLM",
                "p50_ms": 100,
                "p95_ms": 200,
                "mean_ms": 150,
            },
            "tts": {
                "label": "TTS",
                "p50_ms": 30,
                "p95_ms": 60,
                "mean_ms": 45,
            },
            "e2e": {
                "label": "E2E",
                "p50_ms": 140,
                "p95_ms": 280,
                "mean_ms": 210,
            },
        }
        md = lat._render(stats)
        assert "# Àkàndé latency budget" in md
        assert "| STT | 10 | 20 | 15 |" in md
        assert "synthetic" in md
        assert "N = 5" in md


class TestMain:
    def test_writes_output_path(self, tmp_path, capsys):
        out = tmp_path / "latency.md"
        rc = lat.main(
            [
                "--n",
                "3",
                "--output",
                str(out),
            ]
        )
        assert rc == 0
        body = out.read_text()
        assert "STT" in body
        assert "P50" in body
