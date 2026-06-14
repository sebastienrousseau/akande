# Copyright (C) 2026 Sebastien Rousseau.
#
# Licensed under the Apache License, Version 2.0 (the "License").
"""Tests for the STT backend abstraction."""

import dataclasses

import pytest

from akande.stt import (
    get_stt_backend,
)
from akande.stt.base import STTResult


class TestGetBackend:
    def test_default_is_sr(self, monkeypatch):
        monkeypatch.delenv("AKANDE_STT", raising=False)
        assert get_stt_backend().name == "speech_recognition"

    def test_alias_works(self):
        assert get_stt_backend("sr").name == "speech_recognition"

    def test_arg_overrides_env(self, monkeypatch):
        monkeypatch.setenv("AKANDE_STT", "faster_whisper")
        # Override with sr without needing whisper installed.
        assert get_stt_backend("sr").name == "speech_recognition"

    def test_unknown_raises(self):
        with pytest.raises(ValueError):
            get_stt_backend("not-a-real-backend")

    def test_faster_whisper_raises_when_missing(
        self, monkeypatch
    ):
        monkeypatch.setenv("AKANDE_STT", "faster_whisper")
        # faster-whisper isn't installed in CI; backend ctor
        # should raise a helpful ImportError rather than a
        # generic ModuleNotFoundError.
        with pytest.raises(ImportError, match="faster-whisper"):
            get_stt_backend()


class TestResultDataclass:
    def test_immutable(self):
        r = STTResult(text="hi")
        with pytest.raises(dataclasses.FrozenInstanceError):
            r.text = "x"  # type: ignore[misc]
