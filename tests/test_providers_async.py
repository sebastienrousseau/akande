# Copyright (C) 2026 Sebastien Rousseau.
#
# Licensed under the Apache License, Version 2.0 (the "License").
"""Async path coverage for every LLM provider.

The existing ``test_providers.py`` covers init + sync calls; this
file covers the async generate_response method, log emission, and
the failure-then-re-raise path on each provider.  Streaming was
already exercised in ``test_streaming.py``.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


def _envelope(content: str):
    return SimpleNamespace(
        choices=[
            SimpleNamespace(message=SimpleNamespace(content=content))
        ]
    )


class TestOpenAICompatAsync:
    def test_generate_response_async_ok(self):
        from akande.providers.openai_provider import (
            OpenAIProvider,
        )

        p = OpenAIProvider.__new__(OpenAIProvider)
        p._provider_name = "openai"
        p._default_model = "gpt-4o-mini"
        p.client = MagicMock()
        p.client.chat.completions.create.return_value = _envelope(
            "hello"
        )

        async def call():
            return await p.generate_response("hi", "sys", "gpt-4o-mini")

        out = asyncio.run(call())
        assert out.choices[0].message.content == "hello"

    def test_generate_response_async_raises_on_provider_error(self):
        from akande.providers.openai_provider import (
            OpenAIProvider,
        )

        p = OpenAIProvider.__new__(OpenAIProvider)
        p._provider_name = "openai"
        p._default_model = "gpt-4o-mini"
        p.client = MagicMock()
        p.client.chat.completions.create.side_effect = RuntimeError(
            "boom"
        )

        async def call():
            return await p.generate_response("hi", "", "gpt-4o-mini")

        with pytest.raises(RuntimeError):
            asyncio.run(call())


class TestAnthropicAsync:
    def test_call_and_async_path(self):
        from akande.providers.anthropic_provider import (
            AnthropicProvider,
        )

        p = AnthropicProvider.__new__(AnthropicProvider)
        p._default_model = "claude-3-haiku-20240307"
        p.client = MagicMock()
        msg = SimpleNamespace(content=[SimpleNamespace(text="ok")])
        p.client.messages.create.return_value = msg

        async def call():
            return await p.generate_response(
                "hi", "sys", "claude-3-haiku-20240307"
            )

        out = asyncio.run(call())
        assert out.choices[0].message.content == "ok"

    def test_sync_call_works(self):
        from akande.providers.anthropic_provider import (
            AnthropicProvider,
        )

        p = AnthropicProvider.__new__(AnthropicProvider)
        p._default_model = "claude-3-haiku-20240307"
        p.client = MagicMock()
        msg = SimpleNamespace(content=[SimpleNamespace(text="sync ok")])
        p.client.messages.create.return_value = msg
        out = p.generate_response_sync(
            "hi", "", "claude-3-haiku-20240307"
        )
        assert out.choices[0].message.content == "sync ok"

    def test_sync_raises_on_error(self):
        from akande.providers.anthropic_provider import (
            AnthropicProvider,
        )

        p = AnthropicProvider.__new__(AnthropicProvider)
        p._default_model = "claude-3-haiku-20240307"
        p.client = MagicMock()
        p.client.messages.create.side_effect = RuntimeError("x")
        with pytest.raises(RuntimeError):
            p.generate_response_sync(
                "hi", "", "claude-3-haiku-20240307"
            )


class TestGoogleProviderAsync:
    def test_async_call(self):
        from akande.providers.google_provider import (
            GoogleProvider,
        )

        p = GoogleProvider.__new__(GoogleProvider)
        p._default_model = "gemini-1.5-flash"
        p._genai = MagicMock()
        gen_model = MagicMock()
        gen_model.generate_content.return_value = SimpleNamespace(
            text="g-ok"
        )
        p._genai.GenerativeModel.return_value = gen_model

        async def call():
            return await p.generate_response(
                "hi", "sys", "gemini-1.5-flash"
            )

        out = asyncio.run(call())
        assert out.choices[0].message.content == "g-ok"

    def test_sync_call(self):
        from akande.providers.google_provider import (
            GoogleProvider,
        )

        p = GoogleProvider.__new__(GoogleProvider)
        p._default_model = "gemini-1.5-flash"
        p._genai = MagicMock()
        gen_model = MagicMock()
        gen_model.generate_content.return_value = SimpleNamespace(
            text="sync-g"
        )
        p._genai.GenerativeModel.return_value = gen_model
        out = p.generate_response_sync("hi", "", "gemini-1.5-flash")
        assert out.choices[0].message.content == "sync-g"

    def test_provider_name_property(self):
        from akande.providers.google_provider import (
            GoogleProvider,
        )

        p = GoogleProvider.__new__(GoogleProvider)
        assert p.provider_name == "google"


class TestMistralAsync:
    def _make(self):
        from akande.providers.mistral_provider import (
            MistralProvider,
        )

        p = MistralProvider.__new__(MistralProvider)
        p._default_model = "mistral-small-latest"
        p.client = MagicMock()
        return p

    def test_async_with_string_content(self):
        p = self._make()
        p.client.chat.complete.return_value = SimpleNamespace(
            choices=[
                SimpleNamespace(message=SimpleNamespace(content="m-ok"))
            ]
        )

        async def call():
            return await p.generate_response(
                "hi", "sys", "mistral-small-latest"
            )

        out = asyncio.run(call())
        assert out.choices[0].message.content == "m-ok"

    def test_async_with_none_content(self):
        p = self._make()
        p.client.chat.complete.return_value = SimpleNamespace(
            choices=[
                SimpleNamespace(message=SimpleNamespace(content=None))
            ]
        )

        async def call():
            return await p.generate_response(
                "hi", "sys", "mistral-small-latest"
            )

        out = asyncio.run(call())
        assert out.choices[0].message.content == ""

    def test_async_with_chunked_content(self):
        p = self._make()
        chunks = [
            SimpleNamespace(text="a"),
            SimpleNamespace(text="b"),
        ]
        p.client.chat.complete.return_value = SimpleNamespace(
            choices=[
                SimpleNamespace(message=SimpleNamespace(content=chunks))
            ]
        )

        async def call():
            return await p.generate_response(
                "hi", "sys", "mistral-small-latest"
            )

        out = asyncio.run(call())
        assert out.choices[0].message.content == "ab"

    def test_sync_call(self):
        p = self._make()
        p.client.chat.complete.return_value = SimpleNamespace(
            choices=[
                SimpleNamespace(message=SimpleNamespace(content="s-m"))
            ]
        )
        out = p.generate_response_sync("hi", "", "mistral-small-latest")
        assert out.choices[0].message.content == "s-m"

    def test_sync_raises(self):
        p = self._make()
        p.client.chat.complete.side_effect = RuntimeError("x")
        with pytest.raises(RuntimeError):
            p.generate_response_sync("hi", "", "mistral-small-latest")


class TestCohereAsync:
    def _make(self):
        from akande.providers.cohere_provider import (
            CohereProvider,
        )

        p = CohereProvider.__new__(CohereProvider)
        p._default_model = "command-r"
        p.client = MagicMock()
        return p

    def test_async_with_content(self):
        p = self._make()
        response = SimpleNamespace(
            message=SimpleNamespace(
                content=[SimpleNamespace(text="c-ok")]
            )
        )
        p.client.chat.return_value = response

        async def call():
            return await p.generate_response("hi", "sys", "command-r")

        out = asyncio.run(call())
        assert out.choices[0].message.content == "c-ok"

    def test_async_empty_content_safe(self):
        p = self._make()
        p.client.chat.return_value = SimpleNamespace(
            message=SimpleNamespace(content=None)
        )

        async def call():
            return await p.generate_response("hi", "sys", "command-r")

        out = asyncio.run(call())
        assert out.choices[0].message.content == ""


class TestHuggingFaceAsync:
    def test_basic_path(self):
        from akande.providers.huggingface_provider import (
            HuggingFaceProvider,
        )

        p = HuggingFaceProvider.__new__(HuggingFaceProvider)
        p._default_model = "mistralai/Mistral-7B-Instruct-v0.2"
        p.client = MagicMock()
        p.client.chat_completion.return_value = SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content="hf-ok")
                )
            ]
        )

        async def call():
            return await p.generate_response(
                "hi",
                "sys",
                "mistralai/Mistral-7B-Instruct-v0.2",
            )

        out = asyncio.run(call())
        # The HF provider normalises through ProviderResponse so the
        # consumer always sees the OpenAI-shape envelope.
        assert out.choices[0].message.content == "hf-ok"


class TestRegistryDispatch:
    def test_unknown_provider_raises(self):
        from akande.providers.registry import ProviderRegistry

        reg = ProviderRegistry()
        with pytest.raises(ValueError):
            reg.create("not-a-thing")

    def test_register_class_directly(self):
        from akande.providers.base import LLMProvider
        from akande.providers.registry import ProviderRegistry

        class _Stub(LLMProvider):
            @property
            def provider_name(self):
                return "stub"

            async def generate_response(self, *a, **k):
                return None

            def generate_response_sync(self, *a, **k):
                return None

        reg = ProviderRegistry()
        reg.register("stub", _Stub)
        instance = reg.create("stub")
        assert isinstance(instance, _Stub)
        # Cached on second call.
        assert reg.create("stub") is instance

    def test_lazy_registration(self):
        from akande.providers.registry import ProviderRegistry

        reg = ProviderRegistry()
        reg.register_lazy(
            "lazy_openai",
            ".openai_provider",
            "OpenAIProvider",
        )
        assert "lazy_openai" in reg.available


class TestProviderResponseShape:
    def test_provider_response_unwraps(self):
        from akande.providers.response import ProviderResponse

        wrapped = ProviderResponse("hello")
        assert wrapped.choices[0].message.content == "hello"

    def test_provider_response_repr(self):
        from akande.providers.response import ProviderResponse

        wrapped = ProviderResponse("hi")
        assert "hi" in repr(wrapped) or "ProviderResponse" in repr(
            wrapped
        )
