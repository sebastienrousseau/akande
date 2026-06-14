# Copyright (C) 2026 Sebastien Rousseau.
#
# Licensed under the Apache License, Version 2.0 (the "License").
"""VoiceBench runner — score a configured Àkàndé pipeline.

VoiceBench (TACL'26) is the LLM-voice-assistant benchmark; the
reference repo at ``matthewcym/voicebench`` ships 6,783 spoken
instructions across 8 task families.  Their loader reads the
prompts as JSONL with one ``{"prompt", "category"}`` object per
line — that's the shape this runner consumes.

This script does not bundle the prompts (licence + size).  Clone
the upstream once and point this runner at the JSONL::

    git clone https://github.com/matthewcym/voicebench /tmp/vb
    python bench/voicebench/run.py --prompts /tmp/vb/all.jsonl \\
        --provider openai --model gpt-4o-mini \\
        --output bench/voicebench/results-openai-gpt4o-mini.json

The runner is intentionally synchronous and single-threaded so
the cost / wall-clock numbers are reproducible.  Use the
``--limit`` flag to smoke-test against the first N prompts
before paying for the full sweep.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import statistics
import sys
import time
from collections.abc import Iterable
from pathlib import Path
from typing import Any

logger = logging.getLogger("voicebench")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="bench/voicebench/run.py",
        description=__doc__.splitlines()[0],
    )
    p.add_argument(
        "--prompts",
        required=True,
        help="Path to VoiceBench JSONL prompts file",
    )
    p.add_argument(
        "--provider",
        default=os.getenv("LLM_PROVIDER", "openai"),
        help="LLM provider name (matches akande/providers/)",
    )
    p.add_argument(
        "--model",
        default=os.getenv(
            "OPENAI_DEFAULT_MODEL", "gpt-4o-mini"
        ),
        help="Provider-specific model id",
    )
    p.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Score only the first N prompts (0 = all)",
    )
    p.add_argument(
        "--output",
        required=True,
        help="Where to write the JSON results",
    )
    return p.parse_args(argv)


def iter_prompts(
    path: Path, limit: int = 0
) -> Iterable[dict[str, Any]]:
    """Yield ``{prompt, category}`` records from a JSONL file."""
    with path.open("r", encoding="utf-8") as fh:
        for i, line in enumerate(fh):
            if limit and i >= limit:
                return
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                logger.warning(
                    "Skipping malformed prompt on line %d", i
                )


def score_prompt(
    record: dict[str, Any],
    provider: Any,
    model: str,
) -> dict[str, Any]:
    """Score a single prompt.

    The "score" here is the latency + response length; the
    reference VoiceBench harness uses an LLM-as-judge step on top.
    Operators wanting the official numbers should pipe this
    runner's output through that harness — see README.
    """
    prompt = str(record.get("prompt") or "")
    category = str(record.get("category") or "uncategorised")
    start = time.time()
    try:
        from akande.services import SYSTEM_PROMPT

        response = provider.generate_response_sync(
            prompt, SYSTEM_PROMPT, model, None
        )
        text = str(
            response.choices[0].message.content or ""
        )
        ok = True
        error = None
    except Exception as exc:
        text = ""
        ok = False
        error = type(exc).__name__
    latency_ms = (time.time() - start) * 1000.0
    return {
        "category": category,
        "prompt_chars": len(prompt),
        "response_chars": len(text),
        "latency_ms": round(latency_ms, 2),
        "ok": ok,
        "error": error,
    }


def aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute summary stats per category + overall."""
    by_cat: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_cat.setdefault(row["category"], []).append(row)
    out = {
        "overall": _summary(rows),
        "by_category": {
            cat: _summary(items)
            for cat, items in by_cat.items()
        },
    }
    return out


def _summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    ok = [r for r in rows if r["ok"]]
    latencies = [r["latency_ms"] for r in ok]
    char_counts = [r["response_chars"] for r in ok]
    return {
        "count": len(rows),
        "ok": len(ok),
        "ok_rate": (
            round(len(ok) / len(rows), 4) if rows else 0.0
        ),
        "p50_latency_ms": (
            round(
                statistics.median(latencies),
                2,
            )
            if latencies
            else None
        ),
        "p95_latency_ms": (
            round(
                _percentile(latencies, 95),
                2,
            )
            if latencies
            else None
        ),
        "mean_response_chars": (
            round(statistics.mean(char_counts), 1)
            if char_counts
            else None
        ),
    }


def _percentile(
    values: list[float], pct: float
) -> float:
    """Linear-interpolation percentile.  Pure-python so no numpy dep."""
    if not values:
        return 0.0
    s = sorted(values)
    k = (len(s) - 1) * (pct / 100.0)
    lo = int(k)
    hi = min(lo + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def main(argv: list[str] | None = None) -> int:
    ns = parse_args(argv)
    prompts_path = Path(ns.prompts)
    out_path = Path(ns.output)
    if not prompts_path.is_file():
        print(
            f"prompts file not found: {prompts_path}",
            file=sys.stderr,
        )
        return 2
    out_path.parent.mkdir(parents=True, exist_ok=True)

    from akande.providers import get_provider

    provider = get_provider(ns.provider)
    rows: list[dict[str, Any]] = []
    for record in iter_prompts(prompts_path, limit=ns.limit):
        rows.append(score_prompt(record, provider, ns.model))
    payload = {
        "provider": ns.provider,
        "model": ns.model,
        "prompt_count": len(rows),
        "summary": aggregate(rows),
        "rows": rows,
    }
    out_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(
        f"wrote {out_path}  "
        f"(n={len(rows)}  "
        f"ok={payload['summary']['overall']['ok_rate']})"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
