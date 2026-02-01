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


class HuggingFaceProvider(LLMProvider):
    """Hugging Face Inference API provider.

    Env vars: HUGGINGFACE_API_KEY
    """

    @property
    def provider_name(self) -> str:
        return "huggingface"

    def __init__(self):
        try:
            from huggingface_hub import InferenceClient
        except ImportError:
            raise ImportError(
                "The 'huggingface_hub' package is required for "
                "the Hugging Face provider. Install it with: "
                "pip install akande[huggingface]"
            )
        api_key = os.getenv("HUGGINGFACE_API_KEY", "")
        if not api_key:
            raise ValueError(
                "HUGGINGFACE_API_KEY environment variable "
                "is required for the Hugging Face provider."
            )
        self.client = InferenceClient(token=api_key)
        self._default_model = (
            "mistralai/Mistral-7B-Instruct-v0.2"
        )

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
        response = self.client.chat_completion(
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
            max_tokens=1024,
            **params,
        )
        text = response.choices[0].message.content
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
                    "provider": "huggingface",
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
                        "provider": "huggingface",
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
                    "provider": "huggingface",
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
                    "provider": "huggingface",
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
                        "provider": "huggingface",
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
                    "provider": "huggingface",
                    "model": model or self._default_model,
                    "latency_ms": round(latency, 2),
                },
            },
        )
        return response
