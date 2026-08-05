# Copyright (C) 2024 Sebastien Rousseau.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
import asyncio
import logging
import os
import time
from collections.abc import AsyncIterator
from typing import Any

from .base import LLMProvider
from .response import ProviderResponse


class AnthropicProvider(LLMProvider):
    """Anthropic Claude API provider.

    Env vars: ANTHROPIC_API_KEY
    """

    @property
    def provider_name(self) -> str:
        return "anthropic"

    def __init__(self) -> None:
        try:
            import anthropic
        except ImportError as exc:
            raise ImportError(
                "The 'anthropic' package is required for the "
                "Anthropic provider. "
                "Install it with: pip install akande[anthropic]"
            ) from exc
        from akande.config import API_CALL_TIMEOUT

        api_key = os.getenv("ANTHROPIC_API_KEY", "")
        if not api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY environment variable "
                "is required for the Anthropic provider."
            )
        self.client = anthropic.Anthropic(
            api_key=api_key,
            timeout=API_CALL_TIMEOUT,
        )
        self._default_model = "claude-3-haiku-20240307"

    def _call(
        self,
        user_prompt: str,
        system_prompt: str,
        model: str,
        params: dict[str, Any] | None = None,
    ) -> ProviderResponse:
        if not params:
            params = {}
        model = model or self._default_model
        response = self.client.messages.create(
            model=model,
            max_tokens=1024,
            system=system_prompt,
            messages=[
                {"role": "user", "content": user_prompt},
            ],
            **params,
        )
        text = "".join(
            block.text
            for block in response.content
            if hasattr(block, "text")
        )
        return ProviderResponse(text)

    async def generate_response(
        self,
        user_prompt: str,
        system_prompt: str,
        model: str,
        params: dict[str, Any] | None = None,
    ) -> Any:
        logging.info(
            "LLM request sent",
            extra={
                "event": "LLM:RequestSent",
                "extra_data": {
                    "provider": "anthropic",
                    "model": model or self._default_model,
                },
            },
        )
        start = time.time()
        try:
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self._call(
                    user_prompt,
                    system_prompt,
                    model,
                    params,
                ),
            )
        except Exception:  # pragma: no cover - upstream failure logging
            latency = (time.time() - start) * 1000
            logging.error(
                "LLM request failed",
                exc_info=True,
                extra={
                    "event": "LLM:RequestFailed",
                    "extra_data": {
                        "provider": "anthropic",
                        "model": (model or self._default_model),
                        "latency_ms": round(latency, 2),
                    },
                },
            )
            raise
        latency = (time.time() - start) * 1000
        logging.info(
            "LLM response received",
            extra={
                "event": "LLM:ResponseReceived",
                "extra_data": {
                    "provider": "anthropic",
                    "model": model or self._default_model,
                    "latency_ms": round(latency, 2),
                },
            },
        )
        return response

    async def generate_stream(
        self,
        user_prompt: str,
        system_prompt: str,
        model: str,
        params: dict[str, Any] | None = None,
    ) -> AsyncIterator[str]:
        """Native streaming for Anthropic's ``messages.stream`` API.

        The Anthropic SDK exposes a context-manager stream object;
        we drive it on a thread-pool executor and forward
        ``text_stream`` deltas through this async iterator.
        """
        if not params:
            params = {}
        model = model or self._default_model

        logging.info(
            "LLM stream request sent",
            extra={
                "event": "LLM:StreamRequestSent",
                "extra_data": {
                    "provider": "anthropic",
                    "model": model,
                },
            },
        )
        start = time.time()
        loop = asyncio.get_running_loop()

        def _open_stream() -> Any:
            return self.client.messages.stream(
                model=model,
                max_tokens=1024,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": user_prompt},
                ],
                **params,
            )

        try:
            stream_ctx = await loop.run_in_executor(None, _open_stream)
            stream = await loop.run_in_executor(
                None, stream_ctx.__enter__
            )
        except Exception:  # pragma: no cover - upstream failure logging
            latency = (time.time() - start) * 1000
            logging.error(
                "LLM stream open failed",
                exc_info=True,
                extra={
                    "event": "LLM:StreamRequestFailed",
                    "extra_data": {
                        "provider": "anthropic",
                        "model": model,
                        "latency_ms": round(latency, 2),
                    },
                },
            )
            raise

        sentinel: Any = object()
        chunk_count = 0
        try:
            text_iter = iter(stream.text_stream)
            while True:
                item: Any = await loop.run_in_executor(
                    None,
                    lambda: next(text_iter, sentinel),
                )
                if item is sentinel:
                    break
                if item:
                    chunk_count += 1
                    yield item
        finally:
            try:
                await loop.run_in_executor(
                    None,
                    lambda: stream_ctx.__exit__(None, None, None),
                )
            except Exception:  # pragma: no cover - best-effort close
                pass
            latency = (time.time() - start) * 1000
            logging.info(
                "LLM stream completed",
                extra={
                    "event": "LLM:StreamCompleted",
                    "extra_data": {
                        "provider": "anthropic",
                        "model": model,
                        "chunks": chunk_count,
                        "latency_ms": round(latency, 2),
                    },
                },
            )

    async def generate_stream_messages(
        self,
        messages: list[dict[str, str]],
        model: str,
        params: dict[str, Any] | None = None,
    ) -> AsyncIterator[str]:
        """Native multi-turn streaming for Anthropic.

        The Anthropic SDK separates ``system`` (its own kwarg) from
        the conversation messages.  We extract the first ``system``
        message and forward the user/assistant alternation as-is.
        """
        if not params:
            params = {}
        model = model or self._default_model

        system_text = ""
        chat_messages: list[dict[str, str]] = []
        for msg in messages:
            if msg.get("role") == "system" and not system_text:
                system_text = msg.get("content", "")
                continue
            chat_messages.append(
                {
                    "role": msg.get("role", "user"),
                    "content": msg.get("content", ""),
                }
            )

        logging.info(
            "LLM stream request sent",
            extra={
                "event": "LLM:StreamRequestSent",
                "extra_data": {
                    "provider": "anthropic",
                    "model": model,
                    "messages": len(chat_messages),
                },
            },
        )
        start = time.time()
        loop = asyncio.get_running_loop()

        def _open_stream() -> Any:
            return self.client.messages.stream(
                model=model,
                max_tokens=1024,
                system=system_text,
                messages=chat_messages,  # type: ignore[arg-type,unused-ignore]
                **params,
            )

        try:
            stream_ctx = await loop.run_in_executor(None, _open_stream)
            stream = await loop.run_in_executor(
                None, stream_ctx.__enter__
            )
        except Exception:  # pragma: no cover - upstream failure logging
            latency = (time.time() - start) * 1000
            logging.error(
                "LLM stream open failed",
                exc_info=True,
                extra={
                    "event": "LLM:StreamRequestFailed",
                    "extra_data": {
                        "provider": "anthropic",
                        "model": model,
                        "latency_ms": round(latency, 2),
                    },
                },
            )
            raise

        sentinel: Any = object()
        chunk_count = 0
        try:
            text_iter = iter(stream.text_stream)
            while True:
                item: Any = await loop.run_in_executor(
                    None,
                    lambda: next(text_iter, sentinel),
                )
                if item is sentinel:
                    break
                if item:
                    chunk_count += 1
                    yield item
        finally:
            try:
                await loop.run_in_executor(
                    None,
                    lambda: stream_ctx.__exit__(None, None, None),
                )
            except Exception:  # pragma: no cover
                pass
            latency = (time.time() - start) * 1000
            logging.info(
                "LLM stream completed",
                extra={
                    "event": "LLM:StreamCompleted",
                    "extra_data": {
                        "provider": "anthropic",
                        "model": model,
                        "chunks": chunk_count,
                        "latency_ms": round(latency, 2),
                    },
                },
            )

    def generate_response_sync(
        self,
        user_prompt: str,
        system_prompt: str,
        model: str,
        params: dict[str, Any] | None = None,
    ) -> Any:
        logging.info(
            "LLM sync request sent",
            extra={
                "event": "LLM:RequestSent",
                "extra_data": {
                    "provider": "anthropic",
                    "model": model or self._default_model,
                },
            },
        )
        start = time.time()
        try:
            response = self._call(
                user_prompt, system_prompt, model, params
            )
        except Exception:  # pragma: no cover - upstream failure logging
            latency = (time.time() - start) * 1000
            logging.error(
                "LLM sync request failed",
                exc_info=True,
                extra={
                    "event": "LLM:RequestFailed",
                    "extra_data": {
                        "provider": "anthropic",
                        "model": (model or self._default_model),
                        "latency_ms": round(latency, 2),
                    },
                },
            )
            raise
        latency = (time.time() - start) * 1000
        logging.info(
            "LLM sync response received",
            extra={
                "event": "LLM:ResponseReceived",
                "extra_data": {
                    "provider": "anthropic",
                    "model": model or self._default_model,
                    "latency_ms": round(latency, 2),
                },
            },
        )
        return response
