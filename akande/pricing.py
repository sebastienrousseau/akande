# Copyright (C) 2026 Sebastien Rousseau.
#
# Licensed under the Apache License, Version 2.0 (the "License").
"""Static provider price table — last updated 2026-06-14.

Pricing changes quarterly at most upstreams; we ship a snapshot
rather than calling each vendor's billing API at startup.  Prices
are **USD per million tokens** for the model named.  The
``quality_tier`` is Àkàndé's opinion (low / medium / high / top)
and exists so the cost-aware router can answer "cheapest model
that meets a minimum quality" without consulting a benchmark
leaderboard on the hot path.

Update procedure
----------------
1. Pull the latest prices from each provider's pricing page.
2. Bump the file with the new numbers + ``LAST_UPDATED``.
3. Rerun ``pytest tests/test_router.py``.
"""

from __future__ import annotations

from dataclasses import dataclass

LAST_UPDATED = "2026-06-14"

QualityTier = str  # "low" | "medium" | "high" | "top"
_TIER_ORDER = ["low", "medium", "high", "top"]


@dataclass(frozen=True)
class PriceRow:
    """Per-million-token pricing for a single (provider, model)."""

    provider: str
    model: str
    input_per_mtok_usd: float
    output_per_mtok_usd: float
    quality_tier: QualityTier
    local: bool = False


# Provider+model price table.  Local entries have zero marginal
# cost so they always win cost-optimised routing; quality tier is
# the operator's own assessment of the *deployed* local model.
PRICES: list[PriceRow] = [
    # Local providers — zero marginal cost.
    PriceRow("ollama", "llama3.1", 0.0, 0.0, "medium", local=True),
    PriceRow(
        "lmstudio",
        "local-model",
        0.0,
        0.0,
        "medium",
        local=True,
    ),
    # OpenAI (2026-06 published pricing)
    PriceRow("openai", "gpt-4o-mini", 0.15, 0.60, "high"),
    PriceRow("openai", "gpt-4o", 5.00, 15.00, "top"),
    PriceRow("openai", "gpt-3.5-turbo", 0.50, 1.50, "medium"),
    # Anthropic
    PriceRow(
        "anthropic",
        "claude-3-haiku-20240307",
        0.25,
        1.25,
        "high",
    ),
    PriceRow(
        "anthropic",
        "claude-3-5-sonnet-latest",
        3.00,
        15.00,
        "top",
    ),
    # Google
    PriceRow("google", "gemini-1.5-flash", 0.075, 0.30, "high"),
    PriceRow("google", "gemini-1.5-pro", 1.25, 5.00, "top"),
    # Groq (inference-only, very cheap)
    PriceRow("groq", "llama3-8b-8192", 0.05, 0.08, "medium"),
    PriceRow("groq", "llama3-70b-8192", 0.59, 0.79, "high"),
    # Mistral
    PriceRow("mistral", "mistral-small-latest", 0.20, 0.60, "high"),
    PriceRow("mistral", "mistral-large-latest", 2.00, 6.00, "top"),
    # Cohere
    PriceRow("cohere", "command-r", 0.15, 0.60, "high"),
    PriceRow("cohere", "command-r-plus", 2.50, 10.00, "top"),
]


def by_provider() -> dict[str, list[PriceRow]]:
    out: dict[str, list[PriceRow]] = {}
    for row in PRICES:
        out.setdefault(row.provider, []).append(row)
    return out


def expected_cost_per_request(
    row: PriceRow,
    *,
    input_tokens: int = 1500,
    output_tokens: int = 800,
) -> float:
    """Estimate USD cost for a single briefing-shaped request."""
    return (
        row.input_per_mtok_usd * input_tokens / 1_000_000
        + row.output_per_mtok_usd * output_tokens / 1_000_000
    )


def meets_tier(row: PriceRow, minimum: QualityTier) -> bool:
    """Return True when ``row``'s tier is >= ``minimum``."""
    try:
        return _TIER_ORDER.index(row.quality_tier) >= _TIER_ORDER.index(
            minimum
        )
    except ValueError:
        return False


def cheapest_meeting(
    minimum: QualityTier = "medium",
    *,
    local_only: bool = False,
) -> tuple[PriceRow, float] | None:
    """Return the (row, est-cost) tuple for the cheapest qualifier.

    ``local_only=True`` filters to zero-cost local providers — the
    cost-optimised router uses this when ``AKANDE_MODE=offline``
    forbids the cloud options anyway.
    """
    candidates = [
        r
        for r in PRICES
        if meets_tier(r, minimum) and (r.local if local_only else True)
    ]
    if not candidates:
        return None
    scored = [(r, expected_cost_per_request(r)) for r in candidates]
    scored.sort(key=lambda item: (item[1], item[0].provider))
    return scored[0]
