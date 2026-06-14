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
import time
from typing import Any, AsyncIterator, Dict, Optional

from .base import LLMProvider

# Providers that use a local server and do not need a
# real API key.
_LOCAL_PROVIDERS = frozenset({"ollama", "lmstudio"})


class OpenAICompatProvider(LLMProvider):
    """Base class for providers using an OpenAI-compatible API.

    Subclasses only need to set _provider_name, _base_url,
    _api_key, and _default_model in their __init__.
    """

    _provider_name: str = ""
    _base_url: str = ""
    _api_key: str = ""
    _default_model: str = ""

    def _init_client(self) -> None:
        """Initialise the OpenAI-compatible client."""
        import openai
        from akande.config import API_CALL_TIMEOUT

        api_key = self._api_key
        if (
            not api_key
            and self._provider_name in _LOCAL_PROVIDERS
        ):
            api_key = self._provider_name
        elif not api_key:
            raise ValueError(
                f"API key is required for the "
                f"'{self._provider_name}' provider. "
                f"Set the appropriate environment variable."
            )

        kwargs: Dict[str, Any] = {
            "api_key": api_key,
            "timeout": API_CALL_TIMEOUT,
        }
        if self._base_url:
            kwargs["base_url"] = self._base_url
        self.client = openai.OpenAI(**kwargs)

    @property
    def provider_name(self) -> str:
        return self._provider_name

    async def generate_response(
        self,
        user_prompt: str,
        system_prompt: str,
        model: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Any:
        if not params:
            params = {}
        model = model or self._default_model

        logging.info(
            "LLM request sent",
            extra={
                "event": "LLM:RequestSent",
                "extra_data": {
                    "provider": self._provider_name,
                    "model": model,
                },
            },
        )
        start = time.time()
        try:
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.client.chat.completions.create(
                    model=model,
                    messages=[
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
                ),
            )
        except Exception:
            latency = (time.time() - start) * 1000
            logging.error(
                "LLM request failed",
                exc_info=True,
                extra={
                    "event": "LLM:RequestFailed",
                    "extra_data": {
                        "provider": self._provider_name,
                        "model": model,
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
                    "provider": self._provider_name,
                    "model": model,
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
        params: Optional[Dict[str, Any]] = None,
    ) -> AsyncIterator[str]:
        """Native streaming for OpenAI-compatible chat completions.

        Uses ``chat.completions.create(stream=True)`` and yields each
        ``choices[0].delta.content`` chunk as it arrives.  The blocking
        iterator is pumped on a thread-pool executor so concurrent
        callers don't starve the event loop.
        """
        if not params:
            params = {}
        params = {**params, "stream": True}
        model = model or self._default_model

        logging.info(
            "LLM stream request sent",
            extra={
                "event": "LLM:StreamRequestSent",
                "extra_data": {
                    "provider": self._provider_name,
                    "model": model,
                },
            },
        )
        start = time.time()
        loop = asyncio.get_running_loop()

        def _open_stream() -> Any:
            return self.client.chat.completions.create(
                model=model,
                messages=[
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
        except Exception:
            latency = (time.time() - start) * 1000
            logging.error(
                "LLM stream open failed",
                exc_info=True,
                extra={
                    "event": "LLM:StreamRequestFailed",
                    "extra_data": {
                        "provider": self._provider_name,
                        "model": model,
                        "latency_ms": round(latency, 2),
                    },
                },
            )
            raise

        # Pump the synchronous iterator off the event loop one item
        # at a time so we keep the main loop responsive.
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
                    delta = item.choices[0].delta.content or ""
                except (AttributeError, IndexError, TypeError):
                    delta = ""
                if delta:
                    chunk_count += 1
                    yield delta
        finally:
            latency = (time.time() - start) * 1000
            logging.info(
                "LLM stream completed",
                extra={
                    "event": "LLM:StreamCompleted",
                    "extra_data": {
                        "provider": self._provider_name,
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
        params: Optional[Dict[str, Any]] = None,
    ) -> Any:
        if not params:
            params = {}
        model = model or self._default_model

        logging.info(
            "LLM sync request sent",
            extra={
                "event": "LLM:RequestSent",
                "extra_data": {
                    "provider": self._provider_name,
                    "model": model,
                },
            },
        )
        start = time.time()
        try:
            response = self.client.chat.completions.create(
                model=model,
                messages=[
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
        except Exception:
            latency = (time.time() - start) * 1000
            logging.error(
                "LLM sync request failed",
                exc_info=True,
                extra={
                    "event": "LLM:RequestFailed",
                    "extra_data": {
                        "provider": self._provider_name,
                        "model": model,
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
                    "provider": self._provider_name,
                    "model": model,
                    "latency_ms": round(latency, 2),
                },
            },
        )
        return response
