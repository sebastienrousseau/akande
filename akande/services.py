from abc import ABC, abstractmethod
import time
from typing import Any, Dict
import openai
import asyncio
from concurrent.futures import ThreadPoolExecutor
import logging
from .config import OPENAI_DEFAULT_MODEL
from .utils import validate_api_key


class OpenAIService(ABC):
    """Base class for all OpenAI services."""

    @abstractmethod
    async def generate_response(
        self, prompt: str, model: str, parameters: Dict[str, Any]
    ) -> str:
        pass


class OpenAIServiceImpl(OpenAIService):
    """Implementation of the OpenAI service."""

    def __init__(self, api_key: str, rate_limit: int = 60) -> None:
        self.api_key = api_key
        self.rate_limit = rate_limit
        openai.api_key = api_key
        self.requests_count = 0
        self.backoff_factor = 1
        self.executor = ThreadPoolExecutor(max_workers=4)

    async def generate_response(
        self,
        prompt: str,
        model: str = OPENAI_DEFAULT_MODEL,
        parameters: Dict[str, Any] = None,
    ) -> str:
        if parameters is None:
            parameters = {}
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
        combined_prompt = pre_prompt + "\n\n" + prompt

        if "max_tokens" not in parameters:
            parameters["max_tokens"] = 1024
        if not validate_api_key(self.api_key):
            logging.error(
                "Invalid API Key: %s", {"api_key": self.api_key}
            )
            return "Invalid API Key."
        if self.requests_count >= self.rate_limit:
            wait_time = 60 * self.backoff_factor
            logging.warning(
                "Rate limit reached, waiting %s",
                {"wait_time": wait_time},
            )
            await asyncio.sleep(wait_time)
            self.backoff_factor = min(self.backoff_factor * 2, 64)
            self.requests_count = 0
        try:
            start_time = time.time()
            response = await asyncio.get_event_loop().run_in_executor(
                self.executor,
                lambda: openai.Completion.create(
                    engine=model, prompt=combined_prompt, **parameters
                ),
            )
            latency = (
                time.time() - start_time
            ) * 1000  # Convert to milliseconds
            logging.info(
                f"OpenAI API response latency: {latency:.2f} ms"
            )
            response_text = response.choices[0].text.strip()
            self.requests_count += 1
            self.backoff_factor = 1
            return response_text
        except asyncio.TimeoutError:
            logging.error("OpenAI API call timed out")
            return "Sorry, the request timed out. Please try again."
        except openai.OpenAIError as e:
            logging.error("OpenAI API error %s", {"error": str(e)})
            return (
                "Sorry, I'm having some trouble connecting right now."
            )
