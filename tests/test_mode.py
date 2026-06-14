# Copyright (C) 2026 Sebastien Rousseau.
#
# Licensed under the Apache License, Version 2.0 (the "License").
"""Tests for the v0.0.6 AKANDE_MODE=offline switch."""

import pytest

from akande.mode import (
    LOCAL_ONLY_PROVIDERS,
    OFFLINE,
    ONLINE,
    OfflineModeViolation,
    active_mode,
    enforce_for_provider,
    resolve_mode,
)


class TestResolveMode:
    def test_default_is_online(self, monkeypatch):
        monkeypatch.delenv("AKANDE_MODE", raising=False)
        assert resolve_mode() is ONLINE

    def test_explicit_online(self):
        assert resolve_mode("online") is ONLINE

    def test_offline_selected(self):
        assert resolve_mode("offline") is OFFLINE

    def test_case_and_whitespace_insensitive(self):
        assert resolve_mode("  OffLINE\n") is OFFLINE

    def test_unknown_falls_back(self, monkeypatch, caplog):
        monkeypatch.delenv("AKANDE_MODE", raising=False)
        with caplog.at_level("WARNING"):
            assert resolve_mode("hypothetical") is ONLINE
        assert any(
            "Unknown AKANDE_MODE" in r.message
            for r in caplog.records
        )


class TestEnforce:
    def test_online_allows_everything(self, monkeypatch):
        monkeypatch.delenv("AKANDE_MODE", raising=False)
        for name in (
            "openai",
            "anthropic",
            "google",
            "ollama",
            "lmstudio",
            "groq",
        ):
            enforce_for_provider(name)

    def test_offline_blocks_remote(self, monkeypatch):
        monkeypatch.setenv("AKANDE_MODE", "offline")
        for name in (
            "openai",
            "anthropic",
            "google",
            "groq",
            "mistral",
            "cohere",
            "huggingface",
            "azure_openai",
        ):
            with pytest.raises(OfflineModeViolation):
                enforce_for_provider(name)

    def test_offline_allows_local(self, monkeypatch):
        monkeypatch.setenv("AKANDE_MODE", "offline")
        for name in LOCAL_ONLY_PROVIDERS:
            enforce_for_provider(name)
