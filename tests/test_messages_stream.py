# Copyright (C) 2026 Sebastien Rousseau.
#
# Licensed under the Apache License, Version 2.0 (the "License").
"""Tests for the v0.0.6 Track B multi-turn streaming API."""

import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from akande.providers.base import LLMProvider


class _Echo(LLMProvider):
    """Provider that yields the system/user prompt back as one chunk.

    Lets us inspect what the default messages → user_prompt shim does.
    """

    @property
    def provider_name(self) -> str:
        return "echo"

    captured: dict = {}

    async def generate_response(
        self, user_prompt, system_prompt, model, params=None
    ):
        # Not exercised in these tests but required by the ABC.
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content=user_prompt
                    )
                )
            ]
        )

    def generate_response_sync(
        self, user_prompt, system_prompt, model, params=None
    ):
        raise NotImplementedError

    async def generate_stream(
        self,
        user_prompt: str,
        system_prompt: str,
        model: str,
        params=None,
    ):
        # Record so the test can introspect what the default shim
        # collapsed the messages into.
        self.captured = {
            "user_prompt": user_prompt,
            "system_prompt": system_prompt,
        }
        yield user_prompt


class TestDefaultMessagesShim:
    def test_extracts_system_and_last_user(self):
        echo = _Echo()
        msgs = [
            {"role": "system", "content": "you are X"},
            {"role": "user", "content": "older question"},
            {"role": "assistant", "content": "older answer"},
            {"role": "user", "content": "current question"},
        ]

        async def collect():
            out = []
            async for d in echo.generate_stream_messages(
                msgs, "m"
            ):
                out.append(d)
            return out

        asyncio.run(collect())
        assert echo.captured["system_prompt"] == "you are X"
        assert (
            "current question" in echo.captured["user_prompt"]
        )
        # Prior turns are folded into a <previous_conversation> block.
        assert (
            "<previous_conversation>"
            in echo.captured["user_prompt"]
        )
        assert "older answer" in echo.captured["user_prompt"]

    def test_no_history_skips_prior_block(self):
        echo = _Echo()
        msgs = [
            {"role": "system", "content": "X"},
            {"role": "user", "content": "hi"},
        ]

        async def collect():
            async for _ in echo.generate_stream_messages(
                msgs, "m"
            ):
                pass

        asyncio.run(collect())
        assert (
            "<previous_conversation>"
            not in echo.captured["user_prompt"]
        )
        assert echo.captured["user_prompt"] == "hi"

    def test_assistant_only_messages_handled(self):
        echo = _Echo()
        msgs = [
            {"role": "system", "content": "X"},
            {"role": "assistant", "content": "preamble"},
        ]

        async def collect():
            async for _ in echo.generate_stream_messages(
                msgs, "m"
            ):
                pass

        asyncio.run(collect())
        # No trailing user message → current is empty, history kept.
        assert echo.captured["user_prompt"].startswith(
            "<previous_conversation>"
        )


class TestOpenAICompatMessagesNative:
    def _chunk(self, content):
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    delta=SimpleNamespace(content=content)
                )
            ]
        )

    def test_passes_messages_through_unchanged(self):
        from akande.providers.openai_provider import (
            OpenAIProvider,
        )

        provider = OpenAIProvider.__new__(OpenAIProvider)
        provider._provider_name = "openai"
        provider._default_model = "gpt-4o-mini"
        provider.client = MagicMock()
        provider.client.chat.completions.create.return_value = iter(
            [self._chunk("ok")]
        )

        msgs = [
            {"role": "system", "content": "S"},
            {"role": "user", "content": "U1"},
            {"role": "assistant", "content": "A1"},
            {"role": "user", "content": "U2"},
        ]

        async def collect():
            async for _ in provider.generate_stream_messages(
                msgs, "gpt-4o-mini"
            ):
                pass

        asyncio.run(collect())
        call = provider.client.chat.completions.create.call_args
        assert call.kwargs["messages"] == msgs
        assert call.kwargs["stream"] is True
