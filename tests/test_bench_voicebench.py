# Copyright (C) 2026 Sebastien Rousseau.
#
# Licensed under the Apache License, Version 2.0 (the "License").
"""Tests for the VoiceBench runner script."""

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = REPO_ROOT / "bench" / "voicebench" / "run.py"


def _load_runner():
    spec = importlib.util.spec_from_file_location(
        "voicebench_runner", str(RUNNER_PATH)
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


vb = _load_runner()


class TestIterPrompts:
    def test_reads_jsonl(self, tmp_path):
        prompts = tmp_path / "p.jsonl"
        prompts.write_text(
            '{"prompt": "hi", "category": "smalltalk"}\n'
            "\n"
            '{"prompt": "what is QE", "category": "finance"}\n'
        )
        rows = list(vb.iter_prompts(prompts))
        assert [r["category"] for r in rows] == [
            "smalltalk",
            "finance",
        ]

    def test_respects_limit(self, tmp_path):
        prompts = tmp_path / "p.jsonl"
        prompts.write_text(
            '{"prompt": "1", "category": "x"}\n'
            '{"prompt": "2", "category": "x"}\n'
            '{"prompt": "3", "category": "x"}\n'
        )
        rows = list(vb.iter_prompts(prompts, limit=2))
        assert len(rows) == 2

    def test_skips_malformed_lines(self, tmp_path, caplog):
        prompts = tmp_path / "p.jsonl"
        prompts.write_text(
            '{"prompt": "ok", "category": "x"}\n'
            "garbage line\n"
        )
        with caplog.at_level("WARNING"):
            rows = list(vb.iter_prompts(prompts))
        assert len(rows) == 1


class _StubProvider:
    def generate_response_sync(
        self, prompt, system, model, params=None
    ):
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content=f"reply: {prompt}"
                    )
                )
            ]
        )


class _Boom:
    def generate_response_sync(self, *args, **kwargs):
        raise RuntimeError("provider down")


class TestScorePrompt:
    def test_ok_row_shape(self):
        row = vb.score_prompt(
            {"prompt": "hi", "category": "smalltalk"},
            _StubProvider(),
            "m",
        )
        assert row["ok"] is True
        assert row["category"] == "smalltalk"
        assert row["response_chars"] > 0
        assert row["error"] is None
        assert row["latency_ms"] >= 0.0

    def test_provider_error_recorded(self):
        row = vb.score_prompt(
            {"prompt": "hi", "category": "x"},
            _Boom(),
            "m",
        )
        assert row["ok"] is False
        assert row["error"] == "RuntimeError"


class TestAggregate:
    def test_summary_includes_p50_p95(self):
        rows = [
            {
                "category": "a",
                "ok": True,
                "latency_ms": float(i),
                "response_chars": i,
            }
            for i in range(1, 11)
        ]
        summary = vb.aggregate(rows)
        assert summary["overall"]["count"] == 10
        assert summary["overall"]["ok"] == 10
        assert (
            summary["overall"]["p50_latency_ms"]
            == pytest.approx(5.5)
        )
        # P95 of 1..10 (linear interp) ≈ 9.55
        assert (
            summary["overall"]["p95_latency_ms"]
            == pytest.approx(9.55)
        )

    def test_handles_empty(self):
        summary = vb.aggregate([])
        assert summary["overall"]["count"] == 0
        assert summary["overall"]["p50_latency_ms"] is None


class TestMain:
    def test_writes_output_file(self, tmp_path):
        prompts = tmp_path / "p.jsonl"
        prompts.write_text(
            '{"prompt": "hi", "category": "x"}\n'
        )
        out = tmp_path / "results.json"
        with patch.object(
            vb,
            "get_provider",
            create=True,
            return_value=_StubProvider(),
        ):
            # The runner imports get_provider lazily from
            # akande.providers; patch the path it'll resolve.
            with patch(
                "akande.providers.get_provider",
                return_value=_StubProvider(),
            ):
                rc = vb.main(
                    [
                        "--prompts",
                        str(prompts),
                        "--provider",
                        "openai",
                        "--model",
                        "stub",
                        "--output",
                        str(out),
                    ]
                )
        assert rc == 0
        body = json.loads(out.read_text())
        assert body["prompt_count"] == 1
        assert body["model"] == "stub"

    def test_missing_prompts_returns_2(self, tmp_path, capsys):
        rc = vb.main(
            [
                "--prompts",
                str(tmp_path / "nope.jsonl"),
                "--output",
                str(tmp_path / "out.json"),
            ]
        )
        assert rc == 2
