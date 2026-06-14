# Copyright (C) 2026 Sebastien Rousseau.
#
# Licensed under the Apache License, Version 2.0 (the "License").
"""Tests for the sequential STT → LLM → TTS pipeline."""

from unittest.mock import patch

from akande.pipeline import PipelineResult, respond_to_audio
from akande.stt.base import STTResult
from akande.tts.base import TTSSynthesisResult


class _FakeSTT:
    name = "fake_stt"

    def transcribe(
        self, audio, *, fmt="wav", sample_rate=None
    ):
        return STTResult(text="what is QE?", language="en")


class _FakeTTS:
    name = "fake_tts"

    def synthesise(self, text, lang="en"):
        return TTSSynthesisResult(
            audio=b"OUTBOUND" + text.encode(),
            fmt="mp3",
        )


class TestCascade:
    def test_drives_stt_briefing_tts(self, monkeypatch):
        monkeypatch.delenv("AKANDE_S2S", raising=False)
        with patch(
            "akande.pipeline.get_stt_backend",
            return_value=_FakeSTT(),
        ), patch(
            "akande.pipeline.get_tts_backend",
            return_value=_FakeTTS(),
        ), patch(
            "akande.pipeline.get_s2s_provider",
            return_value=None,
        ):
            result = respond_to_audio(
                b"USER", briefing_fn=lambda t: f"Re: {t}"
            )
        assert isinstance(result, PipelineResult)
        assert result.transcript == "what is QE?"
        assert result.reply_text == "Re: what is QE?"
        assert result.audio.startswith(b"OUTBOUND")
        assert result.s2s_used is False
        assert result.fmt == "mp3"

    def test_empty_transcript_default_briefing(
        self, monkeypatch
    ):
        class _Silent:
            def transcribe(
                self, audio, *, fmt="wav", sample_rate=None
            ):
                return STTResult(text="")

        monkeypatch.delenv("AKANDE_S2S", raising=False)
        with patch(
            "akande.pipeline.get_stt_backend",
            return_value=_Silent(),
        ), patch(
            "akande.pipeline.get_tts_backend",
            return_value=_FakeTTS(),
        ), patch(
            "akande.pipeline.get_s2s_provider",
            return_value=None,
        ):
            from akande.pipeline import _default_briefing_fn

            assert "couldn't catch" in _default_briefing_fn(
                ""
            )


class _FakeS2S:
    name = "fake_s2s"

    def respond(self, audio, *, fmt="wav", sample_rate=None):
        from akande.s2s.base import S2SResult

        return S2SResult(
            audio=b"S2S",
            fmt="raw_pcm",
            transcript="hi",
            sample_rate=24_000,
        )


class TestS2SPath:
    def test_s2s_short_circuits_cascade(self, monkeypatch):
        with patch(
            "akande.pipeline.get_s2s_provider",
            return_value=_FakeS2S(),
        ):
            result = respond_to_audio(b"USER")
        assert result.s2s_used is True
        assert result.audio == b"S2S"
        assert result.fmt == "raw_pcm"
        assert result.transcript == "hi"
        assert result.sample_rate == 24_000
