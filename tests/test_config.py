import os
from unittest import mock


def test_config_loads_env_vars():
    with mock.patch.dict(
        os.environ,
        {
            "OPENAI_API_KEY": "sk-test-key-1234567890abcdef",
            "OPENAI_DEFAULT_MODEL": "gpt-4",
        },
    ):
        # Re-import to pick up mocked env
        import importlib
        from akande import config

        importlib.reload(config)
        assert config.OPENAI_API_KEY == "sk-test-key-1234567890abcdef"
        assert config.OPENAI_DEFAULT_MODEL == "gpt-4"


def test_config_defaults():
    with mock.patch.dict(os.environ, {}, clear=True):
        import importlib
        from akande import config

        importlib.reload(config)
        assert config.OPENAI_API_KEY is None
        assert config.OPENAI_DEFAULT_MODEL is None


def test_api_call_timeout():
    from akande.config import API_CALL_TIMEOUT

    assert API_CALL_TIMEOUT == 90
