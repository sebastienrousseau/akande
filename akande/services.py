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
from typing import Any, Dict
import openai
from .config import OPENAI_API_KEY, OPENAI_DEFAULT_MODEL


class OpenAIService(ABC):
    """Base class for OpenAI services."""

    @abstractmethod
    async def generate_response(
        self, prompt: str, model: str, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        pass


class OpenAIImpl(OpenAIService):
    """OpenAI API client implementation."""

    def __init__(self):
        self.client = openai.OpenAI(api_key=OPENAI_API_KEY)

    async def generate_response(
        self,
        user_prompt: str,
        model: str = OPENAI_DEFAULT_MODEL,
        params: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        if not params:
            params = {}

        # Pre-prompt text to guide the AI's response
        pre_prompt = """
        As "Àkàndé," an AI assistant, your mission is to support users by
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
        delivering value by prioritizing essential information relevant to the
        user's needs within 150 words.
        """

        # Combine the pre-prompt with the user's prompt
        full_prompt = pre_prompt + "\n" + user_prompt

        try:
            # Specify the correct method for chat completions
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(
                None,  # Uses default executor
                lambda: self.client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": full_prompt}],
                    **params,
                ),
            )
            return response
        except Exception as exc:
            logging.error("OpenAI API error: %s", exc)
            return {"error": str(exc)}
