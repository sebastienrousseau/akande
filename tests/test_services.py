import asyncio
from unittest.mock import MagicMock, patch

import pytest

from akande.services import (
    OpenAIService,
    OpenAIImpl,
    SYSTEM_PROMPT,
)


class TestSystemPrompt:
    def test_system_prompt_contains_akande(self):
        assert "Àkàndé" in SYSTEM_PROMPT

    def test_system_prompt_contains_structure(self):
        assert "Overview" in SYSTEM_PROMPT
        assert "Solution" in SYSTEM_PROMPT
        assert "Conclusion" in SYSTEM_PROMPT


class TestOpenAIServiceABC:
    def test_cannot_instantiate_abc(self):
        with pytest.raises(TypeError):
            OpenAIService()


class TestOpenAIImpl:
    @patch(
        "akande.services.OPENAI_API_KEY",
        "sk-test-1234567890abcdef",
    )
    @patch("akande.services.openai.OpenAI")
    def test_init_passes_timeout(self, mock_openai_cls):
        OpenAIImpl()
        mock_openai_cls.assert_called_once()
        call_kwargs = mock_openai_cls.call_args.kwargs
        assert "timeout" in call_kwargs

    @patch(
        "akande.services.OPENAI_API_KEY",
        "sk-test-1234567890abcdef",
    )
    @patch("akande.services.openai.OpenAI")
    def test_generate_response_success(self, mock_openai_cls):
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client

        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(message=MagicMock(content="Test response"))
        ]
        mock_client.chat.completions.create.return_value = (
            mock_response
        )

        service = OpenAIImpl()
        result = asyncio.run(
            service.generate_response(
                "Hello",
                SYSTEM_PROMPT,
                "gpt-3.5-turbo",
                {},
            )
        )

        assert result == mock_response
        mock_client.chat.completions.create.assert_called_once()

    @patch(
        "akande.services.OPENAI_API_KEY",
        "sk-test-1234567890abcdef",
    )
    @patch("akande.services.openai.OpenAI")
    def test_generate_response_uses_system_role(
        self, mock_openai_cls
    ):
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client

        mock_response = MagicMock()
        mock_client.chat.completions.create.return_value = (
            mock_response
        )

        service = OpenAIImpl()
        asyncio.run(
            service.generate_response(
                "What is AI?",
                SYSTEM_PROMPT,
                "gpt-4",
                {},
            )
        )

        call_args = mock_client.chat.completions.create.call_args
        messages = call_args.kwargs.get("messages", [])
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert "Àkàndé" in messages[0]["content"]
        assert "What is AI?" in messages[1]["content"]

    @patch(
        "akande.services.OPENAI_API_KEY",
        "sk-test-1234567890abcdef",
    )
    @patch("akande.services.openai.OpenAI")
    def test_generate_response_propagates_exception(
        self, mock_openai_cls
    ):
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create.side_effect = (
            Exception("API error")
        )

        service = OpenAIImpl()
        with pytest.raises(Exception, match="API error"):
            asyncio.run(
                service.generate_response(
                    "Hello",
                    SYSTEM_PROMPT,
                    "gpt-3.5-turbo",
                    {},
                )
            )

    @patch(
        "akande.services.OPENAI_API_KEY",
        "sk-test-1234567890abcdef",
    )
    @patch("akande.services.openai.OpenAI")
    def test_generate_response_sync(self, mock_openai_cls):
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client

        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(message=MagicMock(content="Sync response"))
        ]
        mock_client.chat.completions.create.return_value = (
            mock_response
        )

        service = OpenAIImpl()
        result = service.generate_response_sync(
            "Hello", SYSTEM_PROMPT, "gpt-3.5-turbo", {}
        )

        assert result == mock_response

    @patch(
        "akande.services.OPENAI_API_KEY",
        "sk-test-1234567890abcdef",
    )
    @patch("akande.services.openai.OpenAI")
    def test_sync_uses_system_and_user_roles(
        self, mock_openai_cls
    ):
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client

        mock_response = MagicMock()
        mock_client.chat.completions.create.return_value = (
            mock_response
        )

        service = OpenAIImpl()
        service.generate_response_sync(
            "Test", SYSTEM_PROMPT, "gpt-4", {}
        )

        call_args = mock_client.chat.completions.create.call_args
        messages = call_args.kwargs.get("messages", [])
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
