import inspect


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


class TestKeyboardBindings:
    def test_no_ctrl_v_binding(self):
        from akande.tui import AkandeApp

        keys = [b.key for b in AkandeApp.BINDINGS]
        assert "ctrl+v" not in keys

    def test_no_ctrl_s_binding(self):
        from akande.tui import AkandeApp

        keys = [b.key for b in AkandeApp.BINDINGS]
        assert "ctrl+s" not in keys

    def test_no_ctrl_r_binding(self):
        from akande.tui import AkandeApp

        keys = [b.key for b in AkandeApp.BINDINGS]
        assert "ctrl+r" not in keys

    def test_no_ctrl_w_binding(self):
        from akande.tui import AkandeApp

        keys = [b.key for b in AkandeApp.BINDINGS]
        assert "ctrl+w" not in keys

    def test_escape_binding_exists(self):
        from akande.tui import AkandeApp

        keys = [b.key for b in AkandeApp.BINDINGS]
        assert "escape" in keys

    def test_escape_maps_to_quit(self):
        from akande.tui import AkandeApp

        for b in AkandeApp.BINDINGS:
            if b.key == "escape":
                assert b.action == "quit"

    def test_f1_binding_exists(self):
        from akande.tui import AkandeApp

        keys = [b.key for b in AkandeApp.BINDINGS]
        assert "f1" in keys

    def test_number_bindings_exist(self):
        from akande.tui import AkandeApp

        keys = [b.key for b in AkandeApp.BINDINGS]
        assert "1" in keys
        assert "2" in keys
        assert "3" in keys
        assert "4" in keys


class TestWelcomeMessage:
    def test_welcome_shows_numbered_menu(self):
        from akande.tui import AkandeApp

        src = inspect.getsource(AkandeApp.compose)
        assert "[1]" in src
        assert "[2]" in src

    def test_welcome_no_ctrl_references(self):
        from akande.tui import AkandeApp

        src = inspect.getsource(AkandeApp.compose)
        assert "Ctrl+" not in src
