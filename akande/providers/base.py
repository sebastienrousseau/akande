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
from typing import Any, Dict, Optional


class LLMProvider(ABC):
    """Abstract base class for LLM providers.

    All providers must implement both async and sync response
    generation methods. Implementations should handle their own
    credential loading from environment variables.
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
