# Copyright (C) 2026 Sebastien Rousseau.
#
# Licensed under the Apache License, Version 2.0 (the "License").
"""Tests for the speech-to-speech provider seam."""

import pytest

from akande.s2s import get_s2s_provider
from akande.s2s.base import S2SResult


class TestGetProvider:
    def test_default_returns_none(self, monkeypatch):
        monkeypatch.delenv("AKANDE_S2S", raising=False)
        assert get_s2s_provider() is None

    def test_empty_string_returns_none(self):
        assert get_s2s_provider("") is None

    def test_unknown_raises(self):
        with pytest.raises(ValueError):
            get_s2s_provider("not-real")

    def test_openai_requires_key(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        with pytest.raises(ValueError):
            get_s2s_provider("openai_realtime")

    def test_gemini_skeleton_raises_on_use(self):
        from akande.s2s.gemini_live import GeminiLiveProvider

        with pytest.raises(NotImplementedError):
            GeminiLiveProvider().respond(b"")


class TestResult:
    def test_immutable(self):
        r = S2SResult(audio=b"x", fmt="wav")
        with pytest.raises(Exception):
            r.audio = b"y"  # type: ignore[misc]
