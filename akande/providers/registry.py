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
import importlib
import logging

from .base import LLMProvider

DEFAULT_PROVIDER = "openai"

# Lazy import mapping: provider name -> (module_path, class_name)
_PROVIDER_MAP: dict[str, tuple] = {
    "openai": (
        ".openai_provider",
        "OpenAIProvider",
    ),
    "azure_openai": (
        ".azure_openai_provider",
        "AzureOpenAIProvider",
    ),
    "ollama": (
        ".ollama_provider",
        "OllamaProvider",
    ),
    "lmstudio": (
        ".lmstudio_provider",
        "LMStudioProvider",
    ),
    "groq": (
        ".groq_provider",
        "GroqProvider",
    ),
    "anthropic": (
        ".anthropic_provider",
        "AnthropicProvider",
    ),
    "google": (
        ".google_provider",
        "GoogleProvider",
    ),
    "mistral": (
        ".mistral_provider",
        "MistralProvider",
    ),
    "cohere": (
        ".cohere_provider",
        "CohereProvider",
    ),
    "huggingface": (
        ".huggingface_provider",
        "HuggingFaceProvider",
    ),
}


class ProviderRegistry:
    """Registry for LLM provider implementations.

    Providers are registered lazily by name. The provider module
    is only imported when ``create()`` is first called for that
    name, and the resulting instance is cached for reuse.
    """

    def __init__(
        self,
        lazy_map: dict[str, tuple] | None = None,
    ):
        self._classes: dict[str, type[LLMProvider]] = {}
        self._instances: dict[str, LLMProvider] = {}
        self._lazy_map: dict[str, tuple] = (
            dict(lazy_map) if lazy_map else {}
        )

    def register(
        self,
        name: str,
        cls: type[LLMProvider],
    ) -> None:
        """Register a provider class under the given name."""
        self._classes[name] = cls

    def register_lazy(
        self,
        name: str,
        module_path: str,
        class_name: str,
    ) -> None:
        """Register a provider for lazy import."""
        self._lazy_map[name] = (module_path, class_name)

    @property
    def available(self) -> list[str]:
        """Return list of registered provider names."""
        names = set(self._classes.keys())
        names.update(self._lazy_map.keys())
        return sorted(names)

    def _resolve_class(self, name: str) -> type[LLMProvider]:
        """Resolve a provider class, importing lazily."""
        if name in self._classes:
            return self._classes[name]
        if name in self._lazy_map:
            module_path, class_name = self._lazy_map[name]
            mod = importlib.import_module(
                module_path, package=__package__
            )
            cls = getattr(mod, class_name)
            self._classes[name] = cls
            return cls
        raise ValueError(
            f"Unknown LLM provider: {name!r}. "
            f"Available: {self.available}"
        )

    def create(self, name: str) -> LLMProvider:
        """Get or create a cached provider instance.

        Parameters
        ----------
        name : str
            The registered provider name.

        Returns
        -------
        LLMProvider
            A (cached) instance of the requested provider.

        Raises
        ------
        ValueError
            If the provider name is not registered.
        """
        if name in self._instances:
            return self._instances[name]
        cls = self._resolve_class(name)
        instance = cls()
        self._instances[name] = instance
        return instance


# Module-level singleton registry (lazy -- no provider
# modules imported until first use)
_registry = ProviderRegistry(lazy_map=_PROVIDER_MAP)


def get_provider(name: str = "") -> LLMProvider:
    """Get a provider instance by name.

    If name is empty, reads LLM_PROVIDER from the environment
    (via akande.config), defaulting to 'openai'.

    Parameters
    ----------
    name : str, optional
        The provider name. If empty, uses config.

    Returns
    -------
    LLMProvider
        An instance of the requested provider.
    """
    if not name:
        from akande.config import LLM_PROVIDER

        name = LLM_PROVIDER or DEFAULT_PROVIDER

    # ``AKANDE_MODE=offline`` refuses any non-local provider.  We
    # check at the registry boundary so the rest of the codebase
    # never has to ask "is this allowed?".  Imported lazily to keep
    # the registry import-time-light.
    from akande.mode import enforce_for_provider

    enforce_for_provider(name)

    logging.info(
        "LLM provider resolved",
        extra={
            "event": "Provider:Resolved",
            "extra_data": {
                "provider": name,
                "available": _registry.available,
            },
        },
    )
    return _registry.create(name)
