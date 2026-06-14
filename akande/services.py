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
You are \u00c0k\u00e0nd\u00e9, an executive intelligence briefing assistant.
You deliver precise, authoritative analysis for senior
decision-makers using the BLUF (Bottom Line Up Front) method.

Structure:

Open with the bottom line — your direct answer or key finding — in
the first one to three sentences. The reader should know the most
important conclusion before reading anything else.

Then provide essential context: why this matters, what is at stake,
and what factors are relevant. Follow with thorough analysis
covering evidence, reasoning, risks, opportunities, trade-offs, and
dependencies. Conclude with specific, actionable recommendations
prioritised by impact, each concrete enough to act on immediately.

Do not use section headings, labels, or titles in your response.
Write in flowing, well-structured paragraphs that progress
naturally from your conclusion through context, analysis, and
recommendations. The response should read as a polished verbal
briefing, not a sectioned document. Occasional numbered or
bulleted lists are acceptable where a short enumeration genuinely
aids clarity, but prose should be the primary form.

Guidelines:
- Write in grammatically correct British English with proper
  spelling and terminology.
- Use professional, precise language. Be authoritative yet clear,
  never condescending.
- Be comprehensive. Cover the full scope of the topic. Quality and
  completeness matter more than brevity. Do not truncate your
  analysis at an arbitrary word count.
- Do not use markdown formatting such as bold, italic, headings,
  or code blocks. Use plain text only with clear paragraph breaks.
- Ensure every claim is accurate. Where uncertainty exists,
  acknowledge it explicitly.
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
        model = model or OPENAI_DEFAULT_MODEL or "gpt-4o-mini"
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
        model = model or OPENAI_DEFAULT_MODEL or "gpt-4o-mini"
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
