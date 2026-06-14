# Copyright (C) 2026 Sebastien Rousseau.
#
# Licensed under the Apache License, Version 2.0 (the "License").
"""Multi-turn conversation domain model.

Stores ``Conversation`` and ``Turn`` rows in the SQLite DB managed by
``akande.db.ConversationDB``.  Provides a small CRUD surface used by
the CLI, TUI, and Web UI to maintain context across requests.

Context window strategy
-----------------------
``recent_messages_for_prompt`` returns the last ``limit`` turns in
chronological order.  Summarisation of older context is intentionally
deferred to a later iteration — for v0.0.6-dev.2 we cap at a simple
sliding window which keeps the LLM call deterministic and easy to
test.  The summariser will live on top of this method.
"""

from __future__ import annotations

import logging
import secrets
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from akande.db import ConversationDB

logger = logging.getLogger(__name__)

DEFAULT_USER_ID = "default"
DEFAULT_RECENT_TURNS = 20


@dataclass
class Turn:
    """A single user or assistant turn within a conversation."""

    id: int
    conv_id: str
    role: str
    content: str
    ts: str
    tokens: Optional[int] = None
    cost_usd: Optional[float] = None
    provider: Optional[str] = None
    model: Optional[str] = None

    def to_message(self) -> Dict[str, str]:
        """Render as an OpenAI-style chat message."""
        return {"role": self.role, "content": self.content}


@dataclass
class Conversation:
    """A persisted multi-turn conversation."""

    id: str
    user_id: str
    title: Optional[str]
    created_at: str
    updated_at: str


def new_conversation_id() -> str:
    """Mint a fresh URL-safe conversation identifier.

    Length is chosen to give a low collision probability over the
    expected lifetime of a single Àkàndé instance (~10⁶ conversations)
    while staying short enough to be human-shareable in the Web UI.
    """
    return secrets.token_urlsafe(12)


class ConversationStore:
    """High-level CRUD for conversations and turns.

    This wraps :class:`akande.db.ConversationDB` so business logic
    never touches raw SQL.  All methods are thread-safe via the
    underlying DB lock.
    """

    def __init__(self, db: Optional[ConversationDB] = None) -> None:
        self.db = db or ConversationDB()

    # -- conversations ---------------------------------------------

    def create(
        self,
        user_id: str = DEFAULT_USER_ID,
        title: Optional[str] = None,
        conv_id: Optional[str] = None,
    ) -> Conversation:
        """Create a new conversation row and return it."""
        cid = conv_id or new_conversation_id()
        with self.db.lock:
            self.db.conn.execute(
                "INSERT INTO conversations (id, user_id, title) "
                "VALUES (?, ?, ?)",
                (cid, user_id, title),
            )
        return self._fetch_conversation(cid)

    def get(self, conv_id: str) -> Optional[Conversation]:
        with self.db.lock:
            row = self.db.conn.execute(
                "SELECT id, user_id, title, created_at, "
                "updated_at FROM conversations WHERE id = ?",
                (conv_id,),
            ).fetchone()
        if not row:
            return None
        return Conversation(**dict(row))

    def get_or_create(
        self,
        conv_id: Optional[str],
        user_id: str = DEFAULT_USER_ID,
    ) -> Conversation:
        """Look up or mint a conversation by id.

        If ``conv_id`` is ``None`` or unknown, a fresh row is created
        (using the supplied id when given so callers can pre-allocate
        identifiers client-side).
        """
        if conv_id:
            existing = self.get(conv_id)
            if existing:
                return existing
            return self.create(
                user_id=user_id, conv_id=conv_id
            )
        return self.create(user_id=user_id)

    def list(
        self,
        user_id: str = DEFAULT_USER_ID,
        limit: int = 50,
    ) -> List[Conversation]:
        """Return the user's most recently-updated conversations."""
        with self.db.lock:
            rows = self.db.conn.execute(
                "SELECT id, user_id, title, created_at, "
                "updated_at FROM conversations "
                "WHERE user_id = ? "
                "ORDER BY updated_at DESC LIMIT ?",
                (user_id, limit),
            ).fetchall()
        return [Conversation(**dict(r)) for r in rows]

    def delete(self, conv_id: str) -> None:
        """Delete a conversation and cascade to its turns."""
        with self.db.lock:
            self.db.conn.execute(
                "DELETE FROM conversations WHERE id = ?",
                (conv_id,),
            )

    def set_title(self, conv_id: str, title: str) -> None:
        with self.db.lock:
            self.db.conn.execute(
                "UPDATE conversations "
                "SET title = ?, updated_at = CURRENT_TIMESTAMP "
                "WHERE id = ?",
                (title, conv_id),
            )

    # -- turns -----------------------------------------------------

    def append_turn(
        self,
        conv_id: str,
        role: str,
        content: str,
        *,
        tokens: Optional[int] = None,
        cost_usd: Optional[float] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None,
    ) -> Turn:
        """Append a new turn and bump the conversation's updated_at.

        ``role`` must be one of ``user``, ``assistant``, or
        ``system``; the DB check constraint enforces this.
        """
        if role not in {"user", "assistant", "system"}:
            raise ValueError(
                f"invalid turn role: {role!r}"
            )
        with self.db.lock:
            cur = self.db.conn.execute(
                "INSERT INTO turns (conv_id, role, content, "
                "tokens, cost_usd, provider, model) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    conv_id,
                    role,
                    content,
                    tokens,
                    cost_usd,
                    provider,
                    model,
                ),
            )
            turn_id = cur.lastrowid
            self.db.conn.execute(
                "UPDATE conversations "
                "SET updated_at = CURRENT_TIMESTAMP "
                "WHERE id = ?",
                (conv_id,),
            )
            row = self.db.conn.execute(
                "SELECT id, conv_id, role, content, ts, "
                "tokens, cost_usd, provider, model "
                "FROM turns WHERE id = ?",
                (turn_id,),
            ).fetchone()
        return Turn(**dict(row))

    def recent_turns(
        self,
        conv_id: str,
        limit: int = DEFAULT_RECENT_TURNS,
    ) -> List[Turn]:
        """Return the last ``limit`` turns in chronological order."""
        with self.db.lock:
            rows = self.db.conn.execute(
                "SELECT id, conv_id, role, content, ts, "
                "tokens, cost_usd, provider, model "
                "FROM turns WHERE conv_id = ? "
                "ORDER BY ts DESC LIMIT ?",
                (conv_id, limit),
            ).fetchall()
        return [Turn(**dict(r)) for r in reversed(rows)]

    def recent_messages_for_prompt(
        self,
        conv_id: str,
        limit: int = DEFAULT_RECENT_TURNS,
    ) -> List[Dict[str, str]]:
        """Return recent turns shaped for an LLM ``messages`` arg."""
        return [t.to_message() for t in self.recent_turns(conv_id, limit)]

    def _fetch_conversation(self, conv_id: str) -> Conversation:
        result = self.get(conv_id)
        if result is None:
            # Should not happen — we just inserted.
            raise RuntimeError(
                f"conversation {conv_id!r} vanished after insert"
            )
        return result
