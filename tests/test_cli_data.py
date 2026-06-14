# Copyright (C) 2026 Sebastien Rousseau.
#
# Licensed under the Apache License, Version 2.0 (the "License").
"""Tests for the GDPR data-subject CLI (v0.0.6 Track E)."""

import argparse
import json
from unittest.mock import patch

import pytest

from akande.cli.data import data_command


@pytest.fixture
def isolated_home(tmp_path, monkeypatch):
    """Pin AKANDE_HOME so the ConversationStore writes under tmp."""
    monkeypatch.setenv("AKANDE_HOME", str(tmp_path))
    yield tmp_path


def _ns(**overrides):
    """Build an argparse.Namespace matching the CLI parser."""
    defaults = {
        "data_command": "export",
        "user": "alice",
        "output": None,
        "yes": False,
    }
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


class TestExport:
    def test_writes_to_file_when_output_given(
        self, isolated_home, capsys, tmp_path, monkeypatch
    ):
        # Steer the ConversationStore at a tmp-path DB by patching
        # the default ctor target.
        from akande.cli import data as data_cli
        from akande.conversation import ConversationStore
        from akande.db import ConversationDB

        db = ConversationDB(str(tmp_path / "exp.db"))
        store = ConversationStore(db=db)
        conv = store.create(user_id="alice", title="briefing")
        store.append_turn(conv.id, "user", "hi")

        with patch.object(
            data_cli, "ConversationStore", return_value=store
        ):
            out_path = tmp_path / "dump.json"
            rc = data_command(
                _ns(output=str(out_path), user="alice")
            )
        assert rc == 0
        body = json.loads(out_path.read_text())
        assert body["user_id"] == "alice"
        assert body["conversation_count"] == 1
        assert body["conversations"][0]["turns"][0]["content"] == "hi"

    def test_writes_to_stdout_when_no_output(
        self, isolated_home, capsys, tmp_path
    ):
        from akande.cli import data as data_cli
        from akande.conversation import ConversationStore
        from akande.db import ConversationDB

        db = ConversationDB(str(tmp_path / "exp.db"))
        store = ConversationStore(db=db)
        store.create(user_id="alice")

        with patch.object(
            data_cli, "ConversationStore", return_value=store
        ):
            rc = data_command(_ns(user="alice"))
        captured = capsys.readouterr()
        body = json.loads(captured.out)
        assert body["user_id"] == "alice"
        assert rc == 0


class TestDelete:
    def test_refuses_without_yes(
        self, isolated_home, capsys, tmp_path
    ):
        from akande.cli import data as data_cli
        from akande.conversation import ConversationStore
        from akande.db import ConversationDB

        db = ConversationDB(str(tmp_path / "del.db"))
        store = ConversationStore(db=db)
        store.create(user_id="bob")

        with patch.object(
            data_cli, "ConversationStore", return_value=store
        ):
            rc = data_command(
                _ns(
                    data_command="delete",
                    user="bob",
                    yes=False,
                )
            )
        assert rc == 1
        # Nothing was deleted.
        assert len(store.list(user_id="bob")) == 1

    def test_deletes_when_yes(
        self, isolated_home, capsys, tmp_path
    ):
        from akande.cli import data as data_cli
        from akande.conversation import ConversationStore
        from akande.db import ConversationDB

        db = ConversationDB(str(tmp_path / "del2.db"))
        store = ConversationStore(db=db)
        conv = store.create(user_id="bob")
        store.append_turn(conv.id, "user", "x")

        with patch.object(
            data_cli, "ConversationStore", return_value=store
        ):
            rc = data_command(
                _ns(
                    data_command="delete",
                    user="bob",
                    yes=True,
                )
            )
        assert rc == 0
        assert store.list(user_id="bob") == []

    def test_no_user_is_noop(
        self, isolated_home, capsys, tmp_path
    ):
        from akande.cli import data as data_cli
        from akande.conversation import ConversationStore
        from akande.db import ConversationDB

        db = ConversationDB(str(tmp_path / "del3.db"))
        store = ConversationStore(db=db)

        with patch.object(
            data_cli, "ConversationStore", return_value=store
        ):
            rc = data_command(
                _ns(
                    data_command="delete",
                    user="ghost",
                    yes=True,
                )
            )
        assert rc == 0


class TestUnknownSubcommand:
    def test_returns_usage_exit_code(self):
        rc = data_command(_ns(data_command="bogus"))
        assert rc == 2
