# Copyright (C) 2026 Sebastien Rousseau.
#
# Licensed under the Apache License, Version 2.0 (the "License").
"""Long-term memory integration (Mem0-backed, optional).

Àkàndé carries two layers of state:

- :class:`~akande.conversation.ConversationStore` — *exact* history
  of every turn, by conversation, used to inject recent context
  into the prompt.  This is the v0.0.6-dev.2 layer.
- :class:`MemoryStore` (here) — *summarised* facts about the user
  and their conversations, retrieved by semantic similarity, used
  to give the model durable context across sessions.  Backed by
  Mem0 (`pip install mem0ai`) when available; a silent no-op
  otherwise so the rest of the system never branches on whether
  Mem0 is installed.

The module is intentionally side-effect free at import time: nothing
touches the network or loads a model unless a caller asks for a
:class:`MemoryStore` instance and the operator opted in.

Activation
----------
Memory is **off by default**.  Operators turn it on with::

    export AKANDE_MEMORY=1
    export OPENAI_API_KEY=...      # or other Mem0-supported backend

When ``AKANDE_PROFILE=eu`` or ``strict``, memory is permitted but
the operator is responsible for ensuring the chosen Mem0 backend
honours GDPR (right of access / right to erasure).  The
``akande data export`` / ``akande data delete`` CLI commands will
emit Mem0 calls alongside the SQLite store in v0.0.6-dev.5.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any, List, Optional

logger = logging.getLogger(__name__)

DEFAULT_USER_ID = "default"
DEFAULT_MAX_MEMORIES = 5
DEFAULT_TOKEN_BUDGET = 400  # ~ 300 words, well under any model's ctx


@dataclass(frozen=True)
class MemoryHit:
    """A single retrieved memory plus its similarity score."""

    text: str
    score: float
    memory_id: Optional[str] = None


def _mem0_available() -> bool:
    try:
        import mem0  # noqa: F401
    except ImportError:  # pragma: no cover - dep-presence check
        return False
    return True


def _enabled_via_env() -> bool:
    return os.getenv("AKANDE_MEMORY", "0") == "1"


class MemoryStore:
    """Façade over Mem0 with an honest no-op fallback.

    Construction always succeeds.  When Mem0 isn't installed or the
    operator hasn't opted in, every method returns an empty result
    so call sites never need to branch.
    """

    def __init__(
        self,
        *,
        user_id: str = DEFAULT_USER_ID,
        client: Optional[Any] = None,
    ) -> None:
        self.user_id = user_id
        self._client = client
        self._enabled = False
        if client is not None:
            self._enabled = True
            return
        if not _enabled_via_env():
            return
        if not _mem0_available():
            logger.info(
                "Memory disabled — mem0ai not installed",
                extra={
                    "event": "Memory:NotInstalled",
                },
            )
            return
        try:  # pragma: no cover - mem0 not installed in CI
            from mem0 import Memory

            self._client = Memory()
            self._enabled = True
            logger.info(
                "Memory store initialised",
                extra={
                    "event": "Memory:Initialised",
                    "extra_data": {
                        "user_id": user_id,
                    },
                },
            )
        except Exception as exc:
            logger.warning(
                "Memory init failed — continuing without",
                extra={
                    "event": "Memory:InitFailed",
                    "extra_data": {
                        "error": type(exc).__name__,
                    },
                },
            )

    @property
    def enabled(self) -> bool:
        return self._enabled

    # -- write ------------------------------------------------------

    def remember(
        self,
        text: str,
        *,
        metadata: Optional[dict] = None,
    ) -> None:
        """Persist a memory atom.

        Atoms should be short statements about user preferences,
        facts, or context summaries — not raw conversation turns
        (those live in :class:`~akande.conversation.ConversationStore`).
        """
        if not self._enabled or self._client is None or not text.strip():
            return
        try:
            self._client.add(
                text,
                user_id=self.user_id,
                metadata=metadata or {},
            )
        except Exception as exc:
            logger.warning(
                "Memory add failed",
                extra={
                    "event": "Memory:AddFailed",
                    "extra_data": {
                        "error": type(exc).__name__,
                    },
                },
            )

    # -- read -------------------------------------------------------

    def recall(
        self,
        query: str,
        *,
        limit: int = DEFAULT_MAX_MEMORIES,
    ) -> List[MemoryHit]:
        """Return memories semantically similar to ``query``."""
        if not self._enabled or self._client is None or not query.strip():
            return []
        try:
            raw = self._client.search(
                query, user_id=self.user_id, limit=limit
            )
        except Exception as exc:
            logger.warning(
                "Memory search failed",
                extra={
                    "event": "Memory:SearchFailed",
                    "extra_data": {
                        "error": type(exc).__name__,
                    },
                },
            )
            return []
        return _normalise_hits(raw)

    # -- delete -----------------------------------------------------

    def forget_all(self) -> int:
        """Delete every memory for this user.  Returns the count."""
        if not self._enabled or self._client is None:
            return 0
        try:
            hits = self._client.get_all(
                user_id=self.user_id
            )
            count = 0
            for item in _coerce_iter(hits):
                ident = item.get("id") or item.get(
                    "memory_id"
                )
                if ident:
                    self._client.delete(ident)
                    count += 1
            logger.info(
                "Memory cleared",
                extra={
                    "event": "Memory:Cleared",
                    "extra_data": {
                        "user_id": self.user_id,
                        "count": count,
                    },
                },
            )
            return count
        except Exception as exc:
            logger.warning(
                "Memory forget_all failed",
                extra={
                    "event": "Memory:ForgetFailed",
                    "extra_data": {
                        "error": type(exc).__name__,
                    },
                },
            )
            return 0


def _normalise_hits(raw: Any) -> List[MemoryHit]:
    """Best-effort normalisation of Mem0's varied return shapes."""
    out: List[MemoryHit] = []
    for item in _coerce_iter(raw):
        text = (
            item.get("memory")
            or item.get("text")
            or item.get("content")
            or ""
        )
        score = float(item.get("score", 1.0))
        ident = item.get("id") or item.get("memory_id")
        if text:
            out.append(
                MemoryHit(text=text, score=score, memory_id=ident)
            )
    return out


def _coerce_iter(raw: Any) -> List[dict]:
    """Mem0 SDK has returned dict-of-list, list-of-dict, and bare
    list across versions; normalise to a list of dicts."""
    if isinstance(raw, dict):
        for key in ("results", "memories", "data"):
            if isinstance(raw.get(key), list):
                return [
                    m
                    for m in raw[key]
                    if isinstance(m, dict)
                ]
        return []
    if isinstance(raw, list):
        return [m for m in raw if isinstance(m, dict)]
    return []


def format_for_prompt(
    hits: List[MemoryHit],
    *,
    token_budget: int = DEFAULT_TOKEN_BUDGET,
) -> str:
    """Render hits as a system-prompt block under a token budget.

    Token estimation uses a 4-character-per-token rule of thumb —
    accurate enough for budget enforcement without pulling in a
    real tokeniser.  Hits past the budget are dropped silently so
    the rest of the prompt isn't truncated downstream.
    """
    if not hits:
        return ""
    char_budget = token_budget * 4
    lines: List[str] = []
    used = 0
    for h in hits:
        line = f"- {h.text.strip()}"
        if used + len(line) > char_budget:
            break
        lines.append(line)
        used += len(line)
    if not lines:
        return ""
    return (
        "<long_term_memory>\n"
        "Relevant memories from previous sessions:\n"
        + "\n".join(lines)
        + "\n</long_term_memory>"
    )
