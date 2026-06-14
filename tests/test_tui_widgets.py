# Copyright (C) 2026 Sebastien Rousseau.
#
# Licensed under the Apache License, Version 2.0 (the "License").
"""Coverage for akande.tui — the Textual TUI.

Complements the existing source-inspection tests in test_tui.py
with actual instantiation of the AkandeApp class, exercising the
helper / action surfaces with mocked Textual widgets.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from akande.tui import AkandeApp, _suppress_stderr


class TestSuppressStderr:
    def test_yields_then_restores(self):
        with _suppress_stderr():
            print("anything")

    def test_outer_oserror_path(self):
        with patch(
            "akande.tui.os.open", side_effect=OSError("nope")
        ):
            with _suppress_stderr():
                pass


@pytest.fixture
def app():
    """Construct AkandeApp without running the event loop."""
    akande = MagicMock()
    akande.cache = MagicMock()
    akande.openai_service = MagicMock()
    # AkandeApp.action_quit awaits self.akande.stop_server();
    # AsyncMock makes that await-compatible.
    akande.stop_server = AsyncMock()
    akande.run_server = AsyncMock()
    return AkandeApp(akande)


class TestAkandeAppInit:
    def test_attributes_present(self, app):
        assert app.akande is not None
        assert isinstance(app.CSS, str)
        assert app.TITLE == "Akande"

    def test_history_starts_empty(self, app):
        assert app._history == []


class TestWriteHelpers:
    def test_helpers_dont_crash(self, app):
        with patch.object(
            app, "query_one"
        ) as q:
            log = MagicMock()
            q.return_value = log
            app._write_user("hello")
            app._write_assistant("hi")
            app._write_file("/tmp/x.pdf")
            app._write_error("oops")
            app._write_status("status")
        assert log.write.called

    def test_hide_welcome_invokes_query(self, app):
        with patch.object(
            app, "query_one"
        ) as q:
            q.return_value = MagicMock()
            app._hide_welcome()
        q.assert_called()

    def test_show_and_hide_thinking(self, app):
        with patch.object(
            app, "query_one"
        ) as q:
            q.return_value = MagicMock()
            app._show_thinking()
            app._hide_thinking()


class TestActionsSurface:
    def test_action_quit_calls_exit_and_stop_server(self, app):
        with patch.object(app, "exit") as ex:
            asyncio.run(app.action_quit())
        ex.assert_called()
        app.akande.stop_server.assert_called()
