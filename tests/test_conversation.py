# Copyright (C) 2026 Sebastien Rousseau.
#
# Licensed under the Apache License, Version 2.0 (the "License").
"""Tests for the multi-turn conversation store (v0.0.6 Track B)."""

import os

import pytest

from akande.conversation import (
    DEFAULT_USER_ID,
    ConversationStore,
    new_conversation_id,
)
from akande.db import ConversationDB


@pytest.fixture
def store(tmp_path):
    db = ConversationDB(str(tmp_path / "conversations.db"))
    yield ConversationStore(db=db)
    db.close()


class TestIdMinting:
    def test_returns_url_safe_string(self):
        ident = new_conversation_id()
        assert isinstance(ident, str)
        # urlsafe(12) gives 16 chars of base64url-encoded data
        assert len(ident) == 16
        # No padding, no URL-unsafe chars
        assert "=" not in ident
        assert "+" not in ident
        assert "/" not in ident

    def test_mints_distinct_ids(self):
        seen = {new_conversation_id() for _ in range(50)}
        assert len(seen) == 50


class TestCreateAndGet:
    def test_create_returns_persisted_conversation(self, store):
        conv = store.create()
        assert conv.user_id == DEFAULT_USER_ID
        assert conv.title is None
        roundtrip = store.get(conv.id)
        assert roundtrip is not None
        assert roundtrip.id == conv.id

    def test_get_unknown_returns_none(self, store):
        assert store.get("does-not-exist") is None

    def test_get_or_create_idempotent_when_supplied(self, store):
        first = store.get_or_create(conv_id="explicit-id-1")
        second = store.get_or_create(conv_id="explicit-id-1")
        assert first.id == second.id == "explicit-id-1"

    def test_get_or_create_mints_when_omitted(self, store):
        conv = store.get_or_create(conv_id=None)
        assert conv.id
        assert store.get(conv.id) is not None

    def test_list_filters_by_user(self, store):
        store.create(user_id="alice")
        store.create(user_id="alice")
        store.create(user_id="bob")
        assert len(store.list(user_id="alice")) == 2
        assert len(store.list(user_id="bob")) == 1

    def test_delete_cascades_to_turns(self, store):
        conv = store.create()
        store.append_turn(conv.id, "user", "first")
        store.append_turn(conv.id, "assistant", "second")
        store.delete(conv.id)
        assert store.get(conv.id) is None
        assert store.recent_turns(conv.id) == []

    def test_set_title_persists(self, store):
        conv = store.create()
        store.set_title(conv.id, "Quarterly review")
        roundtrip = store.get(conv.id)
        assert roundtrip is not None
        assert roundtrip.title == "Quarterly review"


class TestTurns:
    def test_append_returns_turn_with_id(self, store):
        conv = store.create()
        turn = store.append_turn(
            conv.id,
            "user",
            "hello",
            provider="openai",
            model="gpt-4o-mini",
        )
        assert turn.id > 0
        assert turn.role == "user"
        assert turn.content == "hello"
        assert turn.provider == "openai"
        assert turn.model == "gpt-4o-mini"

    def test_append_rejects_invalid_role(self, store):
        conv = store.create()
        with pytest.raises(ValueError):
            store.append_turn(conv.id, "robot", "bad role")

    def test_recent_turns_chronological_order(self, store):
        conv = store.create()
        for i in range(5):
            store.append_turn(
                conv.id,
                "user" if i % 2 == 0 else "assistant",
                f"msg-{i}",
            )
        turns = store.recent_turns(conv.id, limit=10)
        contents = [t.content for t in turns]
        assert contents == [
            "msg-0",
            "msg-1",
            "msg-2",
            "msg-3",
            "msg-4",
        ]

    def test_recent_turns_respects_limit(self, store):
        conv = store.create()
        for i in range(10):
            store.append_turn(conv.id, "user", f"msg-{i}")
        turns = store.recent_turns(conv.id, limit=3)
        # The last 3 turns, chronological.
        assert [t.content for t in turns] == [
            "msg-7",
            "msg-8",
            "msg-9",
        ]

    def test_recent_messages_for_prompt_shape(self, store):
        conv = store.create()
        store.append_turn(conv.id, "user", "Q?")
        store.append_turn(conv.id, "assistant", "A.")
        msgs = store.recent_messages_for_prompt(conv.id)
        assert msgs == [
            {"role": "user", "content": "Q?"},
            {"role": "assistant", "content": "A."},
        ]


class TestPersistenceAcrossInstances:
    def test_round_trip_through_disk(self, tmp_path):
        path = str(tmp_path / "persist.db")
        db1 = ConversationDB(path)
        s1 = ConversationStore(db=db1)
        conv = s1.create(title="kept")
        s1.append_turn(conv.id, "user", "hello")
        db1.close()

        db2 = ConversationDB(path)
        s2 = ConversationStore(db=db2)
        try:
            roundtrip = s2.get(conv.id)
            assert roundtrip is not None
            assert roundtrip.title == "kept"
            turns = s2.recent_turns(conv.id)
            assert [t.content for t in turns] == ["hello"]
        finally:
            db2.close()


class TestSchema:
    def test_first_open_sets_user_version(self, tmp_path):
        path = str(tmp_path / "schema.db")
        db = ConversationDB(path)
        try:
            version = db.conn.execute("PRAGMA user_version").fetchone()[
                0
            ]
            assert version == 1
        finally:
            db.close()

    def test_db_file_has_owner_only_perms(self, tmp_path):
        # Best-effort; skip on Windows where os.chmod is no-op.
        if os.name == "nt":
            pytest.skip("Windows permissions differ")
        path = str(tmp_path / "perms.db")
        db = ConversationDB(path)
        try:
            mode = os.stat(path).st_mode & 0o777
            assert mode == 0o600
        finally:
            db.close()
