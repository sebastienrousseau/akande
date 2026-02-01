import inspect
from unittest.mock import MagicMock, patch

from akande.exceptions import LLMError


class TestHandleQuestionUsesAsyncioRun:
    def test_handle_question_uses_asyncio_run(self):
        from akande.tui import AkandeApp

        src = inspect.getsource(
            AkandeApp.handle_question
        )
        assert "asyncio.run(" in src
        assert "new_event_loop" not in src


class TestCancellationOnNewQuestion:
    def test_on_input_submitted_calls_cancel_pending(self):
        from akande.tui import AkandeApp

        src = inspect.getsource(
            AkandeApp.on_input_submitted
        )
        assert "cancel_pending" in src

    def test_on_send_btn_calls_cancel_pending(self):
        from akande.tui import AkandeApp

        src = inspect.getsource(
            AkandeApp.on_button_pressed
        )
        assert "cancel_pending" in src


class TestHandleQuestionCatchesLLMError:
    def test_handle_question_catches_llm_error(self):
        from akande.tui import AkandeApp

        src = inspect.getsource(
            AkandeApp.handle_question
        )
        assert "LLMError" in src
        assert "user_message" in src
