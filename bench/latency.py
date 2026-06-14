# Copyright (C) 2026 Sebastien Rousseau.
#
# Licensed under the Apache License, Version 2.0 (the "License").
"""Latency budget benchmark.

Walks the cascade pipeline N times against a fixed-size synthetic
input and reports P50 / P95 wall-clock per stage.  The output
feeds ``docs/benchmarks/latency.md`` which the README links to so
operators can see the budget poster at a glance.

By default the benchmark uses fakes for STT/LLM/TTS to give an
upper bound on the *orchestration* overhead — when you want real
numbers, pass ``--real`` and a configured provider env.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path
from typing import Any


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="bench/latency.py",
        description=__doc__.splitlines()[0],
    )
    p.add_argument(
        "--n",
        type=int,
        default=50,
        help="Iterations per stage (default 50)",
    )
    p.add_argument(
        "--output",
        default="docs/benchmarks/latency.md",
        help="Where to write the rendered budget poster",
    )
    p.add_argument(
        "--real",
        action="store_true",
        help=(
            "Use the real configured providers instead of "
            "fakes (will incur cost + network traffic)"
        ),
    )
    return p.parse_args(argv)


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    k = (len(s) - 1) * (pct / 100.0)
    lo = int(k)
    hi = min(lo + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def _summary(label: str, values: list[float]) -> dict[str, Any]:
    return {
        "label": label,
        "count": len(values),
        "p50_ms": round(
            statistics.median(values) if values else 0.0,
            2,
        ),
        "p95_ms": round(_percentile(values, 95), 2),
        "mean_ms": round(
            statistics.mean(values) if values else 0.0,
            2,
        ),
    }


def time_calls(fn, n: int) -> list[float]:
    out: list[float] = []
    for _ in range(n):
        start = time.time()
        fn()
        out.append((time.time() - start) * 1000.0)
    return out


def _fake_stt() -> str:
    # Simulate the work of decoding 1 s of audio at WAV-rate.
    time.sleep(0.05)
    return "what is quantitative easing?"


def _fake_llm(prompt: str) -> str:
    time.sleep(0.25)
    return "QE is a monetary policy tool ..." * 10


def _fake_tts(text: str) -> bytes:
    time.sleep(0.15)
    return b"\x00" * (len(text) * 4)


def run(args: argparse.Namespace) -> dict[str, Any]:
    if args.real:
        from akande.config import OPENAI_DEFAULT_MODEL
        from akande.providers import get_provider
        from akande.services import SYSTEM_PROMPT
        from akande.stt import get_stt_backend
        from akande.tts import get_tts_backend

        stt_backend = get_stt_backend()
        tts_backend = get_tts_backend()
        provider = get_provider()
        prompt = "What is quantitative easing?"

        def stt_call() -> str:
            return (
                stt_backend.transcribe(b"\x00" * 32_000, fmt="wav").text
                or prompt
            )

        def llm_call() -> str:
            r = provider.generate_response_sync(
                prompt,
                SYSTEM_PROMPT,
                OPENAI_DEFAULT_MODEL or "gpt-4o-mini",
                None,
            )
            return str(r.choices[0].message.content or "")

        def tts_call() -> bytes:
            return tts_backend.synthesise("hello world").audio
    else:
        stt_call = _fake_stt
        llm_call = lambda: _fake_llm("q")  # noqa: E731
        tts_call = lambda: _fake_tts("hello world")  # noqa: E731

    n = args.n
    stt_ms = time_calls(stt_call, n)
    llm_ms = time_calls(llm_call, n)
    tts_ms = time_calls(tts_call, n)
    e2e_ms = [
        s + llm + t
        for s, llm, t in zip(stt_ms, llm_ms, tts_ms, strict=False)
    ]
    return {
        "mode": "real" if args.real else "synthetic",
        "n": n,
        "stt": _summary("STT", stt_ms),
        "llm": _summary("LLM", llm_ms),
        "tts": _summary("TTS", tts_ms),
        "e2e": _summary("E2E", e2e_ms),
    }


def _render(stats: dict[str, Any]) -> str:
    stages = ["stt", "llm", "tts", "e2e"]
    rows = [
        "| stage | P50 (ms) | P95 (ms) | mean (ms) |",
        "|---|---|---|---|",
    ]
    for stage in stages:
        s = stats[stage]
        rows.append(
            f"| {s['label']} | {s['p50_ms']} | "
            f"{s['p95_ms']} | {s['mean_ms']} |"
        )
    body = (
        f"# Àkàndé latency budget — {stats['mode']} mode\n\n"
        f"_N = {stats['n']} iterations per stage_\n\n"
        + "\n".join(rows)
        + "\n\n"
        "Regenerate this file with:\n\n"
        "```bash\n"
        "python bench/latency.py --n 100"
        + (" --real" if stats["mode"] == "real" else "")
        + " --output docs/benchmarks/latency.md\n"
        "```\n"
    )
    return body


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    stats = run(args)
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(_render(stats), encoding="utf-8")
    print(json.dumps(stats, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
