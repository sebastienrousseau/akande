"""Tests for akande.providers package.

Tests all 10 provider adapters, the registry, the ABC, the
response normalisation layer, and the OpenAI-compatible base.
"""

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from akande.providers.base import LLMProvider
from akande.providers.response import (
    ProviderResponse,
    ProviderChoice,
    ProviderMessage,
)
from akande.providers.registry import (
    ProviderRegistry,
    get_provider,
    DEFAULT_PROVIDER,
    _registry,
)


@pytest.fixture(autouse=True)
def _clear_registry_cache():
    """Clear cached provider instances between tests."""
    _registry._instances.clear()
    yield
    _registry._instances.clear()


# ────────────────────────────────────────────────────────────
# Response normalisation
# ────────────────────────────────────────────────────────────


class TestProviderResponse:
    """Test the ProviderResponse normalisation wrapper."""

    def test_content_accessible(self):
        r = ProviderResponse("hello world")
        assert r.choices[0].message.content == "hello world"

    def test_empty_content(self):
        r = ProviderResponse("")
        assert r.choices[0].message.content == ""

    def test_message_class(self):
        m = ProviderMessage("text")
        assert m.content == "text"

    def test_choice_class(self):
        c = ProviderChoice(ProviderMessage("x"))
        assert c.message.content == "x"


# ────────────────────────────────────────────────────────────
# LLMProvider ABC
# ────────────────────────────────────────────────────────────


class TestLLMProviderABC:
    """Test that LLMProvider cannot be instantiated directly."""

    def test_cannot_instantiate(self):
        with pytest.raises(TypeError):
            LLMProvider()

    def test_concrete_subclass_works(self):
        class Dummy(LLMProvider):
            @property
            def provider_name(self):
                return "dummy"

            async def generate_response(
                self, user_prompt, system_prompt, model,
                params=None,
            ):
                return "ok"

            def generate_response_sync(
                self, user_prompt, system_prompt, model,
                params=None,
            ):
                return "ok"

        d = Dummy()
        assert d.provider_name == "dummy"
        assert d.generate_response_sync("a", "b", "c") == "ok"


# ────────────────────────────────────────────────────────────
# ProviderRegistry
# ────────────────────────────────────────────────────────────


class TestProviderRegistry:

    def test_register_and_create(self):
        reg = ProviderRegistry()

        class FakeProvider(LLMProvider):
            @property
            def provider_name(self):
                return "fake"

            async def generate_response(
                self, up, sp, m, params=None
            ):
                return None

            def generate_response_sync(
                self, up, sp, m, params=None
            ):
                return None

        reg.register("fake", FakeProvider)
        provider = reg.create("fake")
        assert isinstance(provider, FakeProvider)

    def test_create_unknown_raises(self):
        reg = ProviderRegistry()
        with pytest.raises(
            ValueError, match="Unknown LLM provider"
        ):
            reg.create("nonexistent")

    def test_available_lists_registered(self):
        reg = ProviderRegistry()

        class FP(LLMProvider):
            @property
            def provider_name(self):
                return "fp"

            async def generate_response(
                self, up, sp, m, params=None
            ):
                return None

            def generate_response_sync(
                self, up, sp, m, params=None
            ):
                return None

        reg.register("alpha", FP)
        reg.register("beta", FP)
        assert "alpha" in reg.available
        assert "beta" in reg.available

    def test_create_caches_instance(self):
        reg = ProviderRegistry()

        class FP(LLMProvider):
            @property
            def provider_name(self):
                return "fp"

            async def generate_response(
                self, up, sp, m, params=None
            ):
                return None

            def generate_response_sync(
                self, up, sp, m, params=None
            ):
                return None

        reg.register("cached", FP)
        p1 = reg.create("cached")
        p2 = reg.create("cached")
        assert p1 is p2

    def test_lazy_registration(self):
        reg = ProviderRegistry()
        reg.register_lazy(
            "openai",
            ".openai_provider",
            "OpenAIProvider",
        )
        assert "openai" in reg.available

    def test_global_registry_has_10_providers(self):
        assert len(_registry.available) == 10

    def test_global_registry_provider_names(self):
        expected = {
            "openai", "anthropic", "google", "ollama",
            "azure_openai", "mistral", "cohere",
            "huggingface", "groq", "lmstudio",
        }
        assert set(_registry.available) == expected


# ────────────────────────────────────────────────────────────
# get_provider
# ────────────────────────────────────────────────────────────


class TestGetProvider:

    @patch("openai.OpenAI")
    @patch(
        "akande.config.OPENAI_API_KEY",
        "sk-test-1234567890abcdef",
    )
    def test_get_provider_openai(self, mock_openai_cls):
        from akande.providers.openai_provider import (
            OpenAIProvider,
        )
        provider = get_provider("openai")
        assert isinstance(provider, OpenAIProvider)
        assert provider.provider_name == "openai"

    def test_get_provider_unknown_raises(self):
        with pytest.raises(
            ValueError, match="Unknown LLM provider"
        ):
            get_provider("nonexistent_provider")

    @patch("openai.OpenAI")
    @patch(
        "akande.config.OPENAI_API_KEY",
        "sk-test-1234567890abcdef",
    )
    @patch("akande.config.LLM_PROVIDER", "openai")
    def test_get_provider_default_from_config(
        self, mock_openai_cls
    ):
        from akande.providers.openai_provider import (
            OpenAIProvider,
        )
        provider = get_provider()
        assert isinstance(provider, OpenAIProvider)

    @patch("akande.config.LLM_PROVIDER", "")
    @patch("openai.OpenAI")
    @patch(
        "akande.config.OPENAI_API_KEY",
        "sk-test-1234567890abcdef",
    )
    def test_get_provider_empty_falls_back_to_default(
        self, mock_openai_cls
    ):
        provider = get_provider("")
        assert provider.provider_name == "openai"


class TestDefaultProviderConstant:

    def test_default_is_openai(self):
        assert DEFAULT_PROVIDER == "openai"


# ────────────────────────────────────────────────────────────
# OpenAI Provider
# ────────────────────────────────────────────────────────────


class TestOpenAIProvider:

    @patch("openai.OpenAI")
    @patch(
        "akande.config.OPENAI_API_KEY",
        "sk-test-1234567890abcdef",
    )
    def test_provider_name(self, mock_cls):
        from akande.providers.openai_provider import (
            OpenAIProvider,
        )
        assert OpenAIProvider().provider_name == "openai"

    @patch("openai.OpenAI")
    @patch(
        "akande.config.OPENAI_API_KEY",
        "sk-test-1234567890abcdef",
    )
    def test_generate_response_sync(self, mock_cls):
        from akande.providers.openai_provider import (
            OpenAIProvider,
        )
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value = (
            MagicMock()
        )
        p = OpenAIProvider()
        result = p.generate_response_sync(
            "hello", "sys", "gpt-4"
        )
        mock_client.chat.completions.create.assert_called_once()
        assert result is not None

    @patch("openai.OpenAI")
    @patch(
        "akande.config.OPENAI_API_KEY",
        "sk-test-1234567890abcdef",
    )
    def test_generate_response_async(self, mock_cls):
        from akande.providers.openai_provider import (
            OpenAIProvider,
        )
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value = (
            MagicMock()
        )
        p = OpenAIProvider()
        result = asyncio.run(
            p.generate_response("hello", "sys", "gpt-4")
        )
        assert result is not None

    @patch("openai.OpenAI")
    @patch(
        "akande.config.OPENAI_API_KEY",
        "sk-test-1234567890abcdef",
    )
    def test_passes_system_and_user_messages(self, mock_cls):
        from akande.providers.openai_provider import (
            OpenAIProvider,
        )
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value = (
            MagicMock()
        )
        p = OpenAIProvider()
        p.generate_response_sync("user", "system", "gpt-4")
        args = mock_client.chat.completions.create.call_args
        msgs = args.kwargs.get("messages", [])
        assert msgs[0] == {
            "role": "system", "content": "system"
        }
        assert msgs[1] == {
            "role": "user", "content": "user"
        }

    @patch("openai.OpenAI")
    @patch(
        "akande.config.OPENAI_API_KEY",
        "sk-test-1234567890abcdef",
    )
    def test_passes_extra_params(self, mock_cls):
        from akande.providers.openai_provider import (
            OpenAIProvider,
        )
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value = (
            MagicMock()
        )
        p = OpenAIProvider()
        p.generate_response_sync(
            "hi", "sys", "gpt-4", params={"temperature": 0.5}
        )
        args = mock_client.chat.completions.create.call_args
        assert args.kwargs.get("temperature") == 0.5

    @patch("openai.OpenAI")
    @patch(
        "akande.config.OPENAI_DEFAULT_MODEL",
        "gpt-4o",
    )
    @patch(
        "akande.config.OPENAI_API_KEY",
        "sk-test-1234567890abcdef",
    )
    def test_respects_default_model_env(self, mock_cls):
        from akande.providers.openai_provider import (
            OpenAIProvider,
        )
        p = OpenAIProvider()
        assert p._default_model == "gpt-4o"

    @patch("openai.OpenAI")
    @patch(
        "akande.config.OPENAI_API_KEY",
        "sk-test-1234567890abcdef",
    )
    def test_error_logging_on_failure(self, mock_cls):
        from akande.providers.openai_provider import (
            OpenAIProvider,
        )
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.chat.completions.create.side_effect = (
            RuntimeError("api down")
        )
        p = OpenAIProvider()
        with pytest.raises(RuntimeError, match="api down"):
            p.generate_response_sync(
                "hi", "sys", "gpt-4"
            )


# ────────────────────────────────────────────────────────────
# OpenAI-Compatible Providers (Ollama, Groq, LM Studio)
# ────────────────────────────────────────────────────────────


class TestOllamaProvider:

    @patch("openai.OpenAI")
    def test_provider_name(self, mock_cls):
        from akande.providers.ollama_provider import (
            OllamaProvider,
        )
        p = OllamaProvider()
        assert p.provider_name == "ollama"

    @patch("openai.OpenAI")
    def test_default_base_url(self, mock_cls):
        from akande.providers.ollama_provider import (
            OllamaProvider,
        )
        p = OllamaProvider()
        assert p._base_url == "http://localhost:11434/v1"

    @patch.dict(
        "os.environ",
        {"OLLAMA_HOST": "http://remote:11434"},
    )
    @patch("openai.OpenAI")
    def test_custom_host(self, mock_cls):
        from akande.providers.ollama_provider import (
            OllamaProvider,
        )
        p = OllamaProvider()
        assert p._base_url == "http://remote:11434/v1"

    @patch("openai.OpenAI")
    def test_sync_call(self, mock_cls):
        from akande.providers.ollama_provider import (
            OllamaProvider,
        )
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value = (
            MagicMock()
        )
        p = OllamaProvider()
        result = p.generate_response_sync(
            "hi", "sys", "llama3"
        )
        assert result is not None


class TestGroqProvider:

    @patch("openai.OpenAI")
    @patch.dict(
        "os.environ", {"GROQ_API_KEY": "gsk_testkey123"}
    )
    def test_provider_name(self, mock_cls):
        from akande.providers.groq_provider import (
            GroqProvider,
        )
        p = GroqProvider()
        assert p.provider_name == "groq"

    @patch("openai.OpenAI")
    @patch.dict(
        "os.environ", {"GROQ_API_KEY": "gsk_testkey123"}
    )
    def test_base_url(self, mock_cls):
        from akande.providers.groq_provider import (
            GroqProvider,
        )
        p = GroqProvider()
        assert "groq.com" in p._base_url

    @patch("openai.OpenAI")
    @patch.dict(
        "os.environ", {"GROQ_API_KEY": "gsk_testkey123"}
    )
    def test_sync_call(self, mock_cls):
        from akande.providers.groq_provider import (
            GroqProvider,
        )
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value = (
            MagicMock()
        )
        p = GroqProvider()
        result = p.generate_response_sync(
            "hi", "sys", "llama3-8b-8192"
        )
        assert result is not None

    def test_missing_api_key_raises(self):
        from akande.providers.groq_provider import (
            GroqProvider,
        )
        with patch.dict("os.environ", {}, clear=True):
            with patch.dict(
                "os.environ",
                {"GROQ_API_KEY": ""},
            ):
                with pytest.raises(ValueError, match="API key"):
                    GroqProvider()


class TestLMStudioProvider:

    @patch("openai.OpenAI")
    def test_provider_name(self, mock_cls):
        from akande.providers.lmstudio_provider import (
            LMStudioProvider,
        )
        p = LMStudioProvider()
        assert p.provider_name == "lmstudio"

    @patch("openai.OpenAI")
    def test_default_base_url(self, mock_cls):
        from akande.providers.lmstudio_provider import (
            LMStudioProvider,
        )
        p = LMStudioProvider()
        assert p._base_url == "http://localhost:1234/v1"

    @patch.dict(
        "os.environ",
        {"LMSTUDIO_HOST": "http://myhost:5555"},
    )
    @patch("openai.OpenAI")
    def test_custom_host(self, mock_cls):
        from akande.providers.lmstudio_provider import (
            LMStudioProvider,
        )
        p = LMStudioProvider()
        assert p._base_url == "http://myhost:5555/v1"


# ────────────────────────────────────────────────────────────
# Azure OpenAI Provider
# ────────────────────────────────────────────────────────────


class TestAzureOpenAIProvider:

    @patch("openai.AzureOpenAI")
    @patch.dict(
        "os.environ",
        {
            "AZURE_OPENAI_API_KEY": "test-key",
            "AZURE_OPENAI_ENDPOINT": "https://test.azure.com",
        },
    )
    def test_provider_name(self, mock_cls):
        from akande.providers.azure_openai_provider import (
            AzureOpenAIProvider,
        )
        p = AzureOpenAIProvider()
        assert p.provider_name == "azure_openai"

    @patch.dict(
        "os.environ",
        {
            "AZURE_OPENAI_API_KEY": "test-key",
            "AZURE_OPENAI_ENDPOINT": "https://test.openai.azure.com",
            "AZURE_OPENAI_API_VERSION": "2024-02-01",
        },
    )
    @patch("openai.AzureOpenAI")
    def test_reads_env_vars(self, mock_cls):
        from akande.providers.azure_openai_provider import (
            AzureOpenAIProvider,
        )
        p = AzureOpenAIProvider()
        assert p._api_key == "test-key"

    @patch("openai.AzureOpenAI")
    @patch.dict(
        "os.environ",
        {
            "AZURE_OPENAI_API_KEY": "test-key",
            "AZURE_OPENAI_ENDPOINT": "https://test.azure.com",
        },
    )
    def test_sync_call(self, mock_cls):
        from akande.providers.azure_openai_provider import (
            AzureOpenAIProvider,
        )
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value = (
            MagicMock()
        )
        p = AzureOpenAIProvider()
        result = p.generate_response_sync(
            "hi", "sys", "gpt-35-turbo"
        )
        assert result is not None

    @patch.dict(
        "os.environ",
        {"AZURE_OPENAI_ENDPOINT": "https://test.azure.com"},
        clear=False,
    )
    def test_missing_api_key_raises(self):
        from akande.providers.azure_openai_provider import (
            AzureOpenAIProvider,
        )
        import os
        os.environ.pop("AZURE_OPENAI_API_KEY", None)
        with pytest.raises(
            ValueError, match="AZURE_OPENAI_API_KEY"
        ):
            AzureOpenAIProvider()

    @patch.dict(
        "os.environ",
        {"AZURE_OPENAI_API_KEY": "test-key"},
        clear=False,
    )
    def test_missing_endpoint_raises(self):
        from akande.providers.azure_openai_provider import (
            AzureOpenAIProvider,
        )
        import os
        os.environ.pop("AZURE_OPENAI_ENDPOINT", None)
        with pytest.raises(
            ValueError, match="AZURE_OPENAI_ENDPOINT"
        ):
            AzureOpenAIProvider()


# ────────────────────────────────────────────────────────────
# Anthropic Provider
# ────────────────────────────────────────────────────────────


class TestAnthropicProvider:

    @patch("anthropic.Anthropic")
    @patch.dict(
        "os.environ",
        {"ANTHROPIC_API_KEY": "sk-ant-test123"},
    )
    def test_provider_name(self, mock_cls):
        from akande.providers.anthropic_provider import (
            AnthropicProvider,
        )
        p = AnthropicProvider()
        assert p.provider_name == "anthropic"

    @patch("anthropic.Anthropic")
    @patch.dict(
        "os.environ",
        {"ANTHROPIC_API_KEY": "sk-ant-test123"},
    )
    def test_sync_call_returns_provider_response(
        self, mock_cls
    ):
        from akande.providers.anthropic_provider import (
            AnthropicProvider,
        )
        mock_client = MagicMock()
        mock_cls.return_value = mock_client

        mock_block = MagicMock()
        mock_block.text = "hello response"
        mock_response = MagicMock()
        mock_response.content = [mock_block]
        mock_client.messages.create.return_value = (
            mock_response
        )

        p = AnthropicProvider()
        result = p.generate_response_sync(
            "hi", "sys", "claude-3-haiku-20240307"
        )
        assert result.choices[0].message.content == (
            "hello response"
        )

    @patch("anthropic.Anthropic")
    @patch.dict(
        "os.environ",
        {"ANTHROPIC_API_KEY": "sk-ant-test123"},
    )
    def test_async_call(self, mock_cls):
        from akande.providers.anthropic_provider import (
            AnthropicProvider,
        )
        mock_client = MagicMock()
        mock_cls.return_value = mock_client

        mock_block = MagicMock()
        mock_block.text = "async result"
        mock_response = MagicMock()
        mock_response.content = [mock_block]
        mock_client.messages.create.return_value = (
            mock_response
        )

        p = AnthropicProvider()
        result = asyncio.run(
            p.generate_response(
                "hi", "sys", "claude-3-haiku-20240307"
            )
        )
        assert result.choices[0].message.content == (
            "async result"
        )

    @patch("anthropic.Anthropic")
    @patch.dict(
        "os.environ",
        {"ANTHROPIC_API_KEY": "sk-ant-test123"},
    )
    def test_passes_system_as_param(self, mock_cls):
        from akande.providers.anthropic_provider import (
            AnthropicProvider,
        )
        mock_client = MagicMock()
        mock_cls.return_value = mock_client

        mock_block = MagicMock()
        mock_block.text = ""
        mock_response = MagicMock()
        mock_response.content = [mock_block]
        mock_client.messages.create.return_value = (
            mock_response
        )

        p = AnthropicProvider()
        p.generate_response_sync(
            "user msg", "system msg",
            "claude-3-haiku-20240307",
        )
        args = mock_client.messages.create.call_args
        assert args.kwargs.get("system") == "system msg"

    def test_missing_api_key_raises(self):
        from akande.providers.anthropic_provider import (
            AnthropicProvider,
        )
        with patch.dict(
            "os.environ", {"ANTHROPIC_API_KEY": ""}
        ):
            with pytest.raises(
                ValueError, match="ANTHROPIC_API_KEY"
            ):
                AnthropicProvider()

    @patch("anthropic.Anthropic")
    @patch.dict(
        "os.environ",
        {"ANTHROPIC_API_KEY": "sk-ant-test123"},
    )
    def test_error_logging_on_failure(self, mock_cls):
        from akande.providers.anthropic_provider import (
            AnthropicProvider,
        )
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.messages.create.side_effect = (
            RuntimeError("api down")
        )
        p = AnthropicProvider()
        with pytest.raises(RuntimeError, match="api down"):
            p.generate_response_sync(
                "hi", "sys", "claude-3-haiku-20240307"
            )


# ────────────────────────────────────────────────────────────
# Google Gemini Provider
# ────────────────────────────────────────────────────────────


class TestGoogleProvider:

    @patch("google.generativeai.configure")
    @patch("google.generativeai.GenerativeModel")
    @patch.dict(
        "os.environ",
        {"GOOGLE_API_KEY": "test-google-key"},
    )
    def test_provider_name(self, mock_model, mock_configure):
        from akande.providers.google_provider import (
            GoogleProvider,
        )
        p = GoogleProvider()
        assert p.provider_name == "google"

    @patch("google.generativeai.configure")
    @patch("google.generativeai.GenerativeModel")
    @patch.dict(
        "os.environ",
        {"GOOGLE_API_KEY": "test-google-key"},
    )
    def test_sync_call(self, mock_model_cls, mock_configure):
        from akande.providers.google_provider import (
            GoogleProvider,
        )
        mock_model = MagicMock()
        mock_model_cls.return_value = mock_model
        mock_response = MagicMock()
        mock_response.text = "gemini says hi"
        mock_model.generate_content.return_value = (
            mock_response
        )

        p = GoogleProvider()
        result = p.generate_response_sync(
            "hi", "sys", "gemini-pro"
        )
        assert result.choices[0].message.content == (
            "gemini says hi"
        )

    def test_missing_api_key_raises(self):
        from akande.providers.google_provider import (
            GoogleProvider,
        )
        with patch("google.generativeai.configure"):
            with patch.dict(
                "os.environ", {"GOOGLE_API_KEY": ""}
            ):
                with pytest.raises(
                    ValueError, match="GOOGLE_API_KEY"
                ):
                    GoogleProvider()


# ────────────────────────────────────────────────────────────
# Mistral Provider
# ────────────────────────────────────────────────────────────


class TestMistralProvider:

    @patch("mistralai.Mistral")
    @patch.dict(
        "os.environ",
        {"MISTRAL_API_KEY": "test-mistral-key"},
    )
    def test_provider_name(self, mock_cls):
        from akande.providers.mistral_provider import (
            MistralProvider,
        )
        p = MistralProvider()
        assert p.provider_name == "mistral"

    @patch("mistralai.Mistral")
    @patch.dict(
        "os.environ",
        {"MISTRAL_API_KEY": "test-mistral-key"},
    )
    def test_sync_call(self, mock_cls):
        from akande.providers.mistral_provider import (
            MistralProvider,
        )
        mock_client = MagicMock()
        mock_cls.return_value = mock_client

        mock_choice = MagicMock()
        mock_choice.message.content = "mistral response"
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_client.chat.complete.return_value = mock_response

        p = MistralProvider()
        result = p.generate_response_sync(
            "hi", "sys", "mistral-small-latest"
        )
        assert result.choices[0].message.content == (
            "mistral response"
        )

    def test_missing_api_key_raises(self):
        from akande.providers.mistral_provider import (
            MistralProvider,
        )
        with patch.dict(
            "os.environ", {"MISTRAL_API_KEY": ""}
        ):
            with pytest.raises(
                ValueError, match="MISTRAL_API_KEY"
            ):
                MistralProvider()


# ────────────────────────────────────────────────────────────
# Cohere Provider
# ────────────────────────────────────────────────────────────


class TestCohereProvider:

    @patch("cohere.ClientV2")
    @patch.dict(
        "os.environ",
        {"COHERE_API_KEY": "test-cohere-key"},
    )
    def test_provider_name(self, mock_cls):
        from akande.providers.cohere_provider import (
            CohereProvider,
        )
        p = CohereProvider()
        assert p.provider_name == "cohere"

    @patch("cohere.ClientV2")
    @patch.dict(
        "os.environ",
        {"COHERE_API_KEY": "test-cohere-key"},
    )
    def test_sync_call(self, mock_cls):
        from akande.providers.cohere_provider import (
            CohereProvider,
        )
        mock_client = MagicMock()
        mock_cls.return_value = mock_client

        mock_text_block = MagicMock()
        mock_text_block.text = "cohere response"
        mock_msg = MagicMock()
        mock_msg.content = [mock_text_block]
        mock_response = MagicMock()
        mock_response.message = mock_msg
        mock_client.chat.return_value = mock_response

        p = CohereProvider()
        result = p.generate_response_sync(
            "hi", "sys", "command-r"
        )
        assert result.choices[0].message.content == (
            "cohere response"
        )

    def test_missing_api_key_raises(self):
        from akande.providers.cohere_provider import (
            CohereProvider,
        )
        with patch.dict(
            "os.environ", {"COHERE_API_KEY": ""}
        ):
            with pytest.raises(
                ValueError, match="COHERE_API_KEY"
            ):
                CohereProvider()


# ────────────────────────────────────────────────────────────
# Hugging Face Provider
# ────────────────────────────────────────────────────────────


class TestHuggingFaceProvider:

    @patch("huggingface_hub.InferenceClient")
    @patch.dict(
        "os.environ",
        {"HUGGINGFACE_API_KEY": "hf_testtoken123"},
    )
    def test_provider_name(self, mock_cls):
        from akande.providers.huggingface_provider import (
            HuggingFaceProvider,
        )
        p = HuggingFaceProvider()
        assert p.provider_name == "huggingface"

    @patch("huggingface_hub.InferenceClient")
    @patch.dict(
        "os.environ",
        {"HUGGINGFACE_API_KEY": "hf_testtoken123"},
    )
    def test_sync_call(self, mock_cls):
        from akande.providers.huggingface_provider import (
            HuggingFaceProvider,
        )
        mock_client = MagicMock()
        mock_cls.return_value = mock_client

        mock_choice = MagicMock()
        mock_choice.message.content = "hf response"
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_client.chat_completion.return_value = (
            mock_response
        )

        p = HuggingFaceProvider()
        result = p.generate_response_sync(
            "hi", "sys",
            "mistralai/Mistral-7B-Instruct-v0.2",
        )
        assert result.choices[0].message.content == (
            "hf response"
        )

    def test_missing_api_key_raises(self):
        from akande.providers.huggingface_provider import (
            HuggingFaceProvider,
        )
        with patch.dict(
            "os.environ", {"HUGGINGFACE_API_KEY": ""}
        ):
            with pytest.raises(
                ValueError, match="HUGGINGFACE_API_KEY"
            ):
                HuggingFaceProvider()


# ────────────────────────────────────────────────────────────
# Adapter Compliance: all providers share the LLMProvider ABC
# ────────────────────────────────────────────────────────────


class TestAdapterCompliance:
    """Verify every registered provider is a LLMProvider."""

    def test_all_registered_are_llm_providers(self):
        for name in _registry.available:
            cls = _registry._resolve_class(name)
            assert issubclass(cls, LLMProvider), (
                f"{name} ({cls}) is not a LLMProvider subclass"
            )

    def test_all_have_provider_name_property(self):
        for name in _registry.available:
            cls = _registry._resolve_class(name)
            assert hasattr(cls, "provider_name")

    def test_all_have_generate_response(self):
        for name in _registry.available:
            cls = _registry._resolve_class(name)
            assert hasattr(cls, "generate_response")

    def test_all_have_generate_response_sync(self):
        for name in _registry.available:
            cls = _registry._resolve_class(name)
            assert hasattr(cls, "generate_response_sync")


# ────────────────────────────────────────────────────────────
# Import error handling for native SDK providers
# ────────────────────────────────────────────────────────────


class TestImportErrors:
    """Verify clear ImportError for missing optional SDKs."""

    def test_anthropic_import_error(self):
        import sys
        saved = sys.modules.get("anthropic")
        sys.modules["anthropic"] = None
        try:
            from akande.providers.anthropic_provider import (
                AnthropicProvider,
            )
            with pytest.raises(ImportError, match="anthropic"):
                AnthropicProvider()
        finally:
            if saved is not None:
                sys.modules["anthropic"] = saved
            else:
                sys.modules.pop("anthropic", None)

    def test_google_import_error(self):
        import sys
        saved = sys.modules.get("google.generativeai")
        saved_google = sys.modules.get("google")
        sys.modules["google.generativeai"] = None
        sys.modules["google"] = None
        try:
            from akande.providers.google_provider import (
                GoogleProvider,
            )
            with pytest.raises(ImportError):
                GoogleProvider()
        finally:
            if saved is not None:
                sys.modules["google.generativeai"] = saved
            else:
                sys.modules.pop("google.generativeai", None)
            if saved_google is not None:
                sys.modules["google"] = saved_google
            else:
                sys.modules.pop("google", None)

    def test_mistral_import_error(self):
        import sys
        saved = sys.modules.get("mistralai")
        sys.modules["mistralai"] = None
        try:
            from akande.providers.mistral_provider import (
                MistralProvider,
            )
            with pytest.raises(ImportError, match="mistralai"):
                MistralProvider()
        finally:
            if saved is not None:
                sys.modules["mistralai"] = saved
            else:
                sys.modules.pop("mistralai", None)

    def test_cohere_import_error(self):
        import sys
        saved = sys.modules.get("cohere")
        sys.modules["cohere"] = None
        try:
            from akande.providers.cohere_provider import (
                CohereProvider,
            )
            with pytest.raises(ImportError, match="cohere"):
                CohereProvider()
        finally:
            if saved is not None:
                sys.modules["cohere"] = saved
            else:
                sys.modules.pop("cohere", None)

    def test_huggingface_import_error(self):
        import sys
        saved = sys.modules.get("huggingface_hub")
        sys.modules["huggingface_hub"] = None
        try:
            from akande.providers.huggingface_provider import (
                HuggingFaceProvider,
            )
            with pytest.raises(
                ImportError, match="huggingface_hub"
            ):
                HuggingFaceProvider()
        finally:
            if saved is not None:
                sys.modules["huggingface_hub"] = saved
            else:
                sys.modules.pop("huggingface_hub", None)
