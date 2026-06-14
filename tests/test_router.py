# Copyright (C) 2026 Sebastien Rousseau.
#
# Licensed under the Apache License, Version 2.0 (the "License").
"""Tests for akande.router + akande.pricing."""

import pytest

from akande.pricing import (
    PRICES,
    PriceRow,
    cheapest_meeting,
    expected_cost_per_request,
    meets_tier,
)
from akande.router import route


class TestPricingTiers:
    def test_meets_tier_self(self):
        row = PriceRow("x", "y", 1.0, 2.0, "high")
        assert meets_tier(row, "high")
        assert meets_tier(row, "low")
        assert not meets_tier(row, "top")

    def test_meets_tier_unknown_returns_false(self):
        row = PriceRow("x", "y", 1.0, 2.0, "high")
        assert not meets_tier(row, "stratospheric")


class TestCheapest:
    def test_cheapest_medium_is_local(self):
        pick = cheapest_meeting("medium")
        assert pick is not None
        row, cost = pick
        assert row.local is True
        assert cost == 0.0

    def test_cheapest_top_is_remote(self):
        pick = cheapest_meeting("top")
        assert pick is not None
        row, _ = pick
        assert row.quality_tier == "top"

    def test_local_only_filters_cloud(self):
        pick = cheapest_meeting("top", local_only=True)
        # No local model is "top" tier in the shipped table.
        assert pick is None or pick[0].local is True

    def test_expected_cost_scales_linearly(self):
        row = PriceRow("x", "y", 1.0, 2.0, "high")
        cost = expected_cost_per_request(
            row, input_tokens=1_000_000, output_tokens=500_000
        )
        assert cost == pytest.approx(1.0 + 1.0)


class TestRouter:
    def test_passthrough_default(self, monkeypatch):
        monkeypatch.delenv("AKANDE_ROUTER", raising=False)
        monkeypatch.setenv("LLM_PROVIDER", "openai")
        # Need to reimport config since it caches the env at import.
        import importlib
        import akande.config

        importlib.reload(akande.config)
        provider, _ = route()
        assert provider == "openai"

    def test_cost_optimised_picks_local(self, monkeypatch):
        monkeypatch.setenv("AKANDE_ROUTER", "cost_optimised")
        monkeypatch.setenv(
            "AKANDE_ROUTER_MIN_TIER", "medium"
        )
        monkeypatch.delenv("AKANDE_MODE", raising=False)
        provider, model = route()
        # The lowest cost qualifier should be a local row.
        assert provider in {"ollama", "lmstudio"}

    def test_table_loaded(self):
        names = {(r.provider, r.model) for r in PRICES}
        assert ("openai", "gpt-4o-mini") in names
        assert ("anthropic", "claude-3-haiku-20240307") in names
