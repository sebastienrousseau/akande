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
from typing import Any, Dict, Optional

from .base import LLMProvider
from .response import ProviderResponse


class AnthropicProvider(LLMProvider):
    """Anthropic Claude API provider.

    Env vars: ANTHROPIC_API_KEY
    """

    @property
    def provider_name(self) -> str:
        return "anthropic"

    def __init__(self):
        try:
            import anthropic
        except ImportError:
            raise ImportError(
                "The 'anthropic' package is required for the "
                "Anthropic provider. "
                "Install it with: pip install akande[anthropic]"
            )
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
        params: Optional[Dict[str, Any]] = None,
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
        params: Optional[Dict[str, Any]] = None,
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
        except Exception:
            latency = (time.time() - start) * 1000
            logging.error(
                "LLM request failed",
                exc_info=True,
                extra={
                    "event": "LLM:RequestFailed",
                    "extra_data": {
                        "provider": "anthropic",
                        "model": (
                            model or self._default_model
                        ),
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

    def generate_response_sync(
        self,
        user_prompt: str,
        system_prompt: str,
        model: str,
        params: Optional[Dict[str, Any]] = None,
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
        except Exception:
            latency = (time.time() - start) * 1000
            logging.error(
                "LLM sync request failed",
                exc_info=True,
                extra={
                    "event": "LLM:RequestFailed",
                    "extra_data": {
                        "provider": "anthropic",
                        "model": (
                            model or self._default_model
                        ),
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
