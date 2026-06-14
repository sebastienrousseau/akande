# Copyright (C) 2026 Sebastien Rousseau.
#
# Licensed under the Apache License, Version 2.0 (the "License").
"""Tests for the v0.0.6 TTS backend abstraction."""

import dataclasses
from unittest.mock import patch

import pytest

from akande.tts import GTTSBackend, get_tts_backend
from akande.tts.base import TTSSynthesisResult


class TestGetBackend:
    def test_default_is_gtts(self, monkeypatch):
        monkeypatch.delenv("AKANDE_TTS", raising=False)
        backend = get_tts_backend()
        assert backend.name == "gtts"
        assert isinstance(backend, GTTSBackend)

    def test_env_selects_backend(self, monkeypatch):
        monkeypatch.setenv("AKANDE_TTS", "gtts")
        assert get_tts_backend().name == "gtts"

    def test_arg_overrides_env(self, monkeypatch):
        monkeypatch.setenv("AKANDE_TTS", "kokoro")
        # Pass an explicit override that doesn't need kokoro deps.
        assert get_tts_backend("gtts").name == "gtts"

    def test_unknown_name_raises(self, monkeypatch):
        monkeypatch.delenv("AKANDE_TTS", raising=False)
        with pytest.raises(ValueError):
            get_tts_backend("not-a-real-backend")


class TestGTTSBackend:
    def test_synthesise_returns_mp3_bytes(self):
        # Patch the gTTS *source* class — the backend lazy-imports
        # it inside ``synthesise`` so patching ``akande.tts...gTTS``
        # would miss the binding.  Patching ``gtts.gTTS`` swaps
        # the class before the import resolves it.
        backend = GTTSBackend()

        class _FakeTTS:
            def __init__(self, text, lang, tld):
                self.text = text

            def write_to_fp(self, buf):
                buf.write(b"ID3\x03ID3audio")

        with patch("gtts.gTTS", _FakeTTS):
            result = backend.synthesise("hello")
        assert isinstance(result, TTSSynthesisResult)
        assert result.fmt == "mp3"
        assert result.audio.startswith(b"ID3")

    def test_init_records_lang_and_tld(self):
        backend = GTTSBackend(lang="es", tld="es")
        assert backend._default_lang == "es"
        assert backend._tld == "es"


class TestKokoroBackendImportError:
    def test_raises_helpful_message_when_missing(self):
        # kokoro-onnx is not installed in CI; the constructor
        # should raise an ImportError pointing to the install
        # command rather than a generic ModuleNotFoundError.
        from akande.tts.kokoro_backend import KokoroBackend

        with pytest.raises(ImportError, match="kokoro-onnx"):
            KokoroBackend()


class TestGetTTSBackendForKokoro:
    def test_kokoro_selection_raises_when_dep_missing(
        self, monkeypatch
    ):
        monkeypatch.setenv("AKANDE_TTS", "kokoro")
        with pytest.raises(ImportError):
            get_tts_backend()


class TestTTSResultDataclass:
    def test_immutable(self):
        r = TTSSynthesisResult(audio=b"x", fmt="mp3")
        with pytest.raises(dataclasses.FrozenInstanceError):
            r.audio = b"y"  # type: ignore[misc]

    def test_sample_rate_defaults_none(self):
        r = TTSSynthesisResult(audio=b"x", fmt="mp3")
        assert r.sample_rate is None
