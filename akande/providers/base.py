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
from typing import Any, AsyncIterator, Dict, Optional


class LLMProvider(ABC):
    """Abstract base class for LLM providers.

    All providers must implement both async and sync response
    generation methods. Implementations should handle their own
    credential loading from environment variables.

    Streaming is offered as an opt-in capability via
    :meth:`generate_stream`.  Subclasses that have a native streaming
    API are expected to override it; the default implementation
    falls back to :meth:`generate_response` and yields the full text
    as a single chunk so callers can treat every provider uniformly.
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the provider name for logging."""
        ...

    @abstractmethod
    async def generate_response(
        self,
        user_prompt: str,
        system_prompt: str,
        model: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Generate a response asynchronously.

        Parameters
        ----------
        user_prompt : str
            The user's input prompt.
        system_prompt : str
            The system prompt for context.
        model : str
            The model identifier.
        params : dict, optional
            Additional provider-specific parameters.

        Returns
        -------
        Any
            The provider's response object.
        """
        ...

    @abstractmethod
    def generate_response_sync(
        self,
        user_prompt: str,
        system_prompt: str,
        model: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Generate a response synchronously.

        Parameters
        ----------
        user_prompt : str
            The user's input prompt.
        system_prompt : str
            The system prompt for context.
        model : str
            The model identifier.
        params : dict, optional
            Additional provider-specific parameters.

        Returns
        -------
        Any
            The provider's response object.
        """
        ...

    async def generate_stream(
        self,
        user_prompt: str,
        system_prompt: str,
        model: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> AsyncIterator[str]:
        """Yield response content as a stream of text deltas.

        Default implementation: call :meth:`generate_response` and
        yield the full content as one chunk.  Subclasses with native
        SDK streaming should override this to emit incremental
        deltas, so the Web UI can render tokens as they arrive and
        the cascade pipeline can hand partial sentences to TTS.

        The yielded values are **text only** (not provider response
        objects).  ``params`` may include provider-specific options;
        a ``stream=True`` flag is added or set by the subclass as
        appropriate.

        Yields
        ------
        str
            Content deltas in the order they arrive.  An empty
            stream is valid (e.g., if the model emits no text).
        """
        response = await self.generate_response(
            user_prompt, system_prompt, model, params
        )
        text = _extract_text(response)
        if text:
            yield text


def _extract_text(response: Any) -> str:
    """Best-effort extraction of content text from a provider response.

    Supports the OpenAI-shaped envelope (``response.choices[0].
    message.content``) used by the response-normaliser, as well as
    plain strings from providers that already return text.
    """
    if isinstance(response, str):
        return response
    try:
        return response.choices[0].message.content or ""
    except (AttributeError, IndexError, TypeError):
        return ""
