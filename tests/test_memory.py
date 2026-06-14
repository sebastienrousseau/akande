# Copyright (C) 2026 Sebastien Rousseau.
#
# Licensed under the Apache License, Version 2.0 (the "License").
"""Tests for the Mem0-backed memory façade (v0.0.6 Track B)."""

from unittest.mock import MagicMock, patch

import pytest

from akande.memory import (
    MemoryHit,
    MemoryStore,
    _normalise_hits,
    format_for_prompt,
)


class TestDisabledByDefault:
    def test_no_client_when_env_unset(self, monkeypatch):
        monkeypatch.delenv("AKANDE_MEMORY", raising=False)
        store = MemoryStore()
        assert store.enabled is False
        assert store.recall("anything") == []
        assert store.forget_all() == 0
        # remember() is a silent no-op.
        store.remember("fact")

    def test_no_client_when_mem0_missing(self, monkeypatch):
        monkeypatch.setenv("AKANDE_MEMORY", "1")
        # Patch the availability check directly.
        with patch(
            "akande.memory._mem0_available",
            return_value=False,
        ):
            store = MemoryStore()
        assert store.enabled is False


class TestExplicitClient:
    def test_remember_calls_add(self):
        client = MagicMock()
        store = MemoryStore(user_id="alice", client=client)
        store.remember("she likes Q3 briefings")
        client.add.assert_called_once()
        kwargs = client.add.call_args.kwargs
        assert kwargs["user_id"] == "alice"

    def test_recall_normalises_results(self):
        client = MagicMock()
        client.search.return_value = {
            "results": [
                {"memory": "first", "score": 0.9, "id": "1"},
                {"memory": "second", "score": 0.7, "id": "2"},
            ]
        }
        store = MemoryStore(client=client)
        hits = store.recall("q")
        assert [h.text for h in hits] == ["first", "second"]
        assert hits[0].score == pytest.approx(0.9)
        assert hits[0].memory_id == "1"

    def test_recall_swallows_exceptions(self):
        client = MagicMock()
        client.search.side_effect = RuntimeError("boom")
        store = MemoryStore(client=client)
        # Must not raise — we degrade silently.
        assert store.recall("q") == []

    def test_forget_all_deletes_each(self):
        client = MagicMock()
        client.get_all.return_value = [
            {"id": "a"},
            {"id": "b"},
            {"memory_id": "c"},
        ]
        store = MemoryStore(client=client)
        assert store.forget_all() == 3
        assert client.delete.call_count == 3


class TestNormaliseHits:
    def test_dict_with_results_key(self):
        raw = {
            "results": [
                {"text": "T", "score": 0.5},
            ]
        }
        assert _normalise_hits(raw)[0].text == "T"

    def test_list_of_dicts(self):
        raw = [{"content": "hello", "score": 1.0}]
        assert _normalise_hits(raw)[0].text == "hello"

    def test_garbage_returns_empty(self):
        assert _normalise_hits("string") == []
        assert _normalise_hits(None) == []


class TestFormatForPrompt:
    def test_empty_returns_empty(self):
        assert format_for_prompt([]) == ""

    def test_hits_get_bullet_lines(self):
        hits = [
            MemoryHit(text="a", score=1.0),
            MemoryHit(text="b", score=0.9),
        ]
        out = format_for_prompt(hits)
        assert "<long_term_memory>" in out
        assert "- a" in out
        assert "- b" in out

    def test_token_budget_caps_lines(self):
        # ~ 4 chars/token, budget=2 tokens ⇒ ~8 chars usable.
        hits = [
            MemoryHit(text="aaaaaaaaaa", score=1.0),  # 10 chars
            MemoryHit(text="bbbbbbbbbb", score=0.9),
        ]
        out = format_for_prompt(hits, token_budget=2)
        # First hit alone exceeds the budget, so no lines fit.
        assert out == ""
