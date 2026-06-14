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


class MistralProvider(LLMProvider):
    """Mistral AI API provider.

    Env vars: MISTRAL_API_KEY
    """

    @property
    def provider_name(self) -> str:
        return "mistral"

    def __init__(self) -> None:
        try:
            from mistralai import Mistral
        except ImportError as exc:
            raise ImportError(
                "The 'mistralai' package is required for the "
                "Mistral provider. "
                "Install it with: pip install akande[mistral]"
            ) from exc
        api_key = os.getenv("MISTRAL_API_KEY", "")
        if not api_key:
            raise ValueError(
                "MISTRAL_API_KEY environment variable "
                "is required for the Mistral provider."
            )
        self.client = Mistral(api_key=api_key)
        self._default_model = "mistral-small-latest"

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
        response = self.client.chat.complete(
            model=model,
            messages=[  # type: ignore[arg-type, unused-ignore]
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": user_prompt,
                },
            ],
            **params,
        )
        raw = response.choices[0].message.content
        # Mistral v1 returns str | content-block list | Unset | None.
        # For the Akande BLUF use case we expect plain text.
        if isinstance(raw, str):
            text = raw
        elif raw is None:
            text = ""
        else:
            text = "".join(getattr(chunk, "text", "") for chunk in raw)
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
                    "provider": "mistral",
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
                        "provider": "mistral",
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
                    "provider": "mistral",
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
        """Native streaming for Mistral v1+ ``client.chat.stream``."""
        if not params:
            params = {}
        model = model or self._default_model

        logging.info(
            "LLM stream request sent",
            extra={
                "event": "LLM:StreamRequestSent",
                "extra_data": {
                    "provider": "mistral",
                    "model": model,
                },
            },
        )
        start = time.time()
        loop = asyncio.get_running_loop()

        def _open_stream() -> Any:
            return self.client.chat.stream(
                model=model,
                messages=[  # type: ignore[arg-type, unused-ignore]
                    {
                        "role": "system",
                        "content": system_prompt,
                    },
                    {
                        "role": "user",
                        "content": user_prompt,
                    },
                ],
                **params,
            )

        try:
            stream = await loop.run_in_executor(None, _open_stream)
        except Exception:  # pragma: no cover - upstream failure logging
            latency = (time.time() - start) * 1000
            logging.error(
                "LLM stream open failed",
                exc_info=True,
                extra={
                    "event": "LLM:StreamRequestFailed",
                    "extra_data": {
                        "provider": "mistral",
                        "model": model,
                        "latency_ms": round(latency, 2),
                    },
                },
            )
            raise

        sentinel: Any = object()
        chunk_count = 0
        try:
            while True:
                item: Any = await loop.run_in_executor(
                    None, lambda: next(stream, sentinel)
                )
                if item is sentinel:
                    break
                delta = ""
                try:
                    delta = item.data.choices[0].delta.content or ""
                except (AttributeError, IndexError, TypeError):
                    delta = ""
                if delta and isinstance(delta, str):
                    chunk_count += 1
                    yield delta
        finally:
            latency = (time.time() - start) * 1000
            logging.info(
                "LLM stream completed",
                extra={
                    "event": "LLM:StreamCompleted",
                    "extra_data": {
                        "provider": "mistral",
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
                    "provider": "mistral",
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
                        "provider": "mistral",
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
                    "provider": "mistral",
                    "model": model or self._default_model,
                    "latency_ms": round(latency, 2),
                },
            },
        )
        return response
