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
from abc import ABC, abstractmethod
import asyncio
import logging
import time
from typing import Any, Dict, Optional
import openai
from .config import (
    OPENAI_API_KEY,
    OPENAI_DEFAULT_MODEL,
    API_CALL_TIMEOUT,
)

SYSTEM_PROMPT = """
As "\u00c0k\u00e0nd\u00e9," an AI assistant, your mission is to support users
providing accurate information on various topics, condensed into a
concise yet comprehensive briefing. Respond only in grammatically
correct British English using proper spelling and local terminology.

Adhere to a 150-word structure:

Overview
- Briefly introduce the topic and frame the key question(s) to be
addressed, highlighting relevance to the user.

Solution
- Offer an actionable response using bullet points for clarity.
- Outline technical solutions or conceptual recommendations.

Conclusion
- Concisely summarize 2-3 most important conclusions or next steps
for the user.

Recommendations
- Provide helpful recommendations based on the information presented.

Use straightforward language suitable for a middle-school audience.
Avoid profanity or potentially insensitive language. Focus on
delivering value by prioritising essential information relevant to the
user's needs within 150 words.
""".strip()


class OpenAIService(ABC):
    """Base class for OpenAI services.

    Retained for backward compatibility. New code should use
    akande.providers.LLMProvider instead.
    """

    @abstractmethod
    async def generate_response(
        self,
        prompt: str,
        system_prompt: str = "",
        model: str = "",
        params: Optional[Dict[str, Any]] = None,
    ) -> Any:
        pass


class OpenAIImpl(OpenAIService):
    """OpenAI API client implementation.

    Retained for backward compatibility. Delegates to
    akande.providers.openai_provider.OpenAIProvider internally.
    """

    def __init__(self):
        self.client = openai.OpenAI(
            api_key=OPENAI_API_KEY,
            timeout=API_CALL_TIMEOUT,
        )

    async def generate_response(
        self,
        user_prompt: str,
        system_prompt: str = "",
        model: str = "",
        params: Optional[Dict[str, Any]] = None,
    ) -> Any:
        if not params:
            params = {}
        model = model or OPENAI_DEFAULT_MODEL
        system_prompt = system_prompt or SYSTEM_PROMPT

        logging.info(
            "LLM request sent",
            extra={
                "event": "LLM:RequestSent",
                "extra_data": {
                    "provider": "openai",
                    "model": model,
                },
            },
        )
        start = time.time()
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
                    {"role": "user", "content": user_prompt},
                ],
                **params,
            ),
        )
        latency = (time.time() - start) * 1000
        logging.info(
            "LLM response received",
            extra={
                "event": "LLM:ResponseReceived",
                "extra_data": {
                    "provider": "openai",
                    "model": model,
                    "latency_ms": round(latency, 2),
                },
            },
        )
        return response

    def generate_response_sync(
        self,
        user_prompt: str,
        system_prompt: str = "",
        model: str = "",
        params: Optional[Dict[str, Any]] = None,
    ) -> Any:
        if not params:
            params = {}
        model = model or OPENAI_DEFAULT_MODEL
        system_prompt = system_prompt or SYSTEM_PROMPT

        logging.info(
            "LLM sync request sent",
            extra={
                "event": "LLM:RequestSent",
                "extra_data": {
                    "provider": "openai",
                    "model": model,
                },
            },
        )
        start = time.time()
        response = self.client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {"role": "user", "content": user_prompt},
            ],
            **params,
        )
        latency = (time.time() - start) * 1000
        logging.info(
            "LLM sync response received",
            extra={
                "event": "LLM:ResponseReceived",
                "extra_data": {
                    "provider": "openai",
                    "model": model,
                    "latency_ms": round(latency, 2),
                },
            },
        )
        return response
