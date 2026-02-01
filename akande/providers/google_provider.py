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


class GoogleProvider(LLMProvider):
    """Google Gemini API provider.

    Env vars: GOOGLE_API_KEY
    """

    @property
    def provider_name(self) -> str:
        return "google"

    def __init__(self):
        try:
            import google.generativeai as genai
        except ImportError:
            raise ImportError(
                "The 'google-generativeai' package is required "
                "for the Google provider. "
                "Install it with: pip install akande[google]"
            )
        api_key = os.getenv("GOOGLE_API_KEY", "")
        if not api_key:
            raise ValueError(
                "GOOGLE_API_KEY environment variable "
                "is required for the Google provider."
            )
        genai.configure(api_key=api_key)
        self._genai = genai
        self._default_model = "gemini-pro"

    def _call(
        self,
        user_prompt: str,
        system_prompt: str,
        model: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> ProviderResponse:
        if not params:
            params = {}
        model_name = model or self._default_model
        gen_model = self._genai.GenerativeModel(
            model_name=model_name,
            system_instruction=system_prompt,
        )
        response = gen_model.generate_content(
            user_prompt, **params
        )
        text = (
            response.text if hasattr(response, "text") else ""
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
                    "provider": "google",
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
                        "provider": "google",
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
                    "provider": "google",
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
                    "provider": "google",
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
                        "provider": "google",
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
                    "provider": "google",
                    "model": model or self._default_model,
                    "latency_ms": round(latency, 2),
                },
            },
        )
        return response
