# Copyright (C) 2026 Sebastien Rousseau.
#
# Licensed under the Apache License, Version 2.0 (the "License").
"""Tests for the v0.0.6 Track B streaming surface.

Covers the LLMProvider.generate_stream contract (default fallback +
native streaming for the OpenAI-compatible providers) and the
async-to-sync bridge used by the SSE endpoint.
"""

import asyncio
from collections.abc import AsyncIterator
from types import SimpleNamespace
from unittest.mock import MagicMock

from akande.providers.base import LLMProvider, _extract_text
from akande.server.server import _sync_iter_async


class _RecordingProvider(LLMProvider):
    """Minimal provider used to exercise the base-class default."""

    @property
    def provider_name(self) -> str:
        return "recording"

    async def generate_response(
        self, user_prompt, system_prompt, model, params=None
    ):
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content="full response")
                )
            ]
        )

    def generate_response_sync(
        self, user_prompt, system_prompt, model, params=None
    ):
        return self.generate_response(
            user_prompt, system_prompt, model, params
        )


class TestExtractText:
    def test_plain_string_returned_as_is(self):
        assert _extract_text("hello") == "hello"

    def test_openai_envelope_unwrapped(self):
        envelope = SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content="hi there")
                )
            ]
        )
        assert _extract_text(envelope) == "hi there"

    def test_unknown_shape_returns_empty(self):
        assert _extract_text(object()) == ""

    def test_empty_choices_returns_empty(self):
        envelope = SimpleNamespace(choices=[])
        assert _extract_text(envelope) == ""


class TestBaseGenerateStreamDefault:
    """The ABC's default generate_stream should yield a single chunk."""

    def test_yields_whole_response_once(self):
        provider = _RecordingProvider()

        async def collect():
            chunks = []
            async for delta in provider.generate_stream(
                "q", "sys", "model"
            ):
                chunks.append(delta)
            return chunks

        chunks = asyncio.run(collect())
        assert chunks == ["full response"]

    def test_empty_response_yields_nothing(self):
        class Silent(_RecordingProvider):
            async def generate_response(
                self,
                user_prompt,
                system_prompt,
                model,
                params=None,
            ):
                return SimpleNamespace(
                    choices=[
                        SimpleNamespace(
                            message=SimpleNamespace(content="")
                        )
                    ]
                )

        async def collect():
            chunks = []
            async for delta in Silent().generate_stream("q", "s", "m"):
                chunks.append(delta)
            return chunks

        assert asyncio.run(collect()) == []


class TestOpenAICompatStreaming:
    """Native streaming via chat.completions.create(stream=True)."""

    def _make_chunk(self, content):
        return SimpleNamespace(
            choices=[
                SimpleNamespace(delta=SimpleNamespace(content=content))
            ]
        )

    def test_yields_each_delta(self):
        from akande.providers.openai_provider import (
            OpenAIProvider,
        )

        provider = OpenAIProvider.__new__(OpenAIProvider)
        provider._provider_name = "openai"
        provider._default_model = "gpt-4o-mini"

        deltas = ["He", "llo, ", "world."]
        provider.client = MagicMock()
        provider.client.chat.completions.create.return_value = iter(
            self._make_chunk(d) for d in deltas
        )

        async def collect():
            chunks = []
            async for delta in provider.generate_stream(
                "Hi", "system", "gpt-4o-mini"
            ):
                chunks.append(delta)
            return chunks

        chunks = asyncio.run(collect())
        assert chunks == ["He", "llo, ", "world."]

        call = provider.client.chat.completions.create.call_args
        assert call.kwargs["stream"] is True
        assert call.kwargs["model"] == "gpt-4o-mini"

    def test_skips_empty_deltas(self):
        from akande.providers.groq_provider import (
            GroqProvider,
        )

        provider = GroqProvider.__new__(GroqProvider)
        provider._provider_name = "groq"
        provider._default_model = "llama3-8b-8192"

        chunks_in = [
            self._make_chunk("Hello"),
            self._make_chunk(None),  # ignored
            self._make_chunk(""),  # ignored
            self._make_chunk(" world"),
        ]
        provider.client = MagicMock()
        provider.client.chat.completions.create.return_value = iter(
            chunks_in
        )

        async def collect():
            out = []
            async for delta in provider.generate_stream(
                "Hi", "", "llama3-8b-8192"
            ):
                out.append(delta)
            return out

        assert asyncio.run(collect()) == ["Hello", " world"]


class TestSyncIterAsync:
    """The CherryPy bridge that drives an async iter from sync code."""

    def test_passes_through_strings(self):
        async def agen() -> AsyncIterator[str]:
            for s in ["a", "b", "c"]:
                yield s

        assert list(_sync_iter_async(agen())) == ["a", "b", "c"]

    def test_empty_iter_yields_nothing(self):
        async def agen() -> AsyncIterator[str]:
            if False:
                yield ""  # pragma: no cover

        assert list(_sync_iter_async(agen())) == []
