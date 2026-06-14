# Copyright (C) 2026 Sebastien Rousseau.
#
# Licensed under the Apache License, Version 2.0 (the "License").
"""``akande data {export, delete}`` — GDPR data subject controls.

These commands operate on the ConversationStore and let an operator
satisfy Articles 15 (right of access) and 17 (right to erasure)
without writing SQL.  The implementation is deliberately small —
formats are JSON, output goes to stdout by default, deletion is
opt-in via ``--yes`` so a typo can't wipe a user's history.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from typing import Any

from akande.conversation import ConversationStore
from akande.memory import MemoryStore


def _dump_user(
    store: ConversationStore,
    user_id: str,
    *,
    memory: MemoryStore | None = None,
) -> dict[str, Any]:
    """Build the JSON dump for a single data subject.

    Includes:

    - every conversation owned by ``user_id`` and all of its turns
      (Article 15: right of access to the categories of personal
      data processed)
    - every Mem0 memory atom for that user when a memory store is
      active (long-term inferred facts also fall under Article 15)
    """
    conversations = store.list(user_id=user_id, limit=10_000)
    out: list[dict[str, Any]] = []
    for conv in conversations:
        turns = store.recent_turns(conv.id, limit=100_000)
        out.append(
            {
                "conversation": dataclasses.asdict(conv),
                "turns": [
                    dataclasses.asdict(t) for t in turns
                ],
            }
        )

    memories: list[dict[str, Any]] = []
    memory_enabled = False
    if memory is not None and memory.enabled:
        memory_enabled = True
        for hit in memory.recall(
            "", limit=10_000
        ) or []:
            memories.append(
                {
                    "text": hit.text,
                    "score": hit.score,
                    "memory_id": hit.memory_id,
                }
            )

    return {
        "user_id": user_id,
        "conversation_count": len(out),
        "conversations": out,
        "memory_enabled": memory_enabled,
        "memory_count": len(memories),
        "memories": memories,
    }


def data_command(ns: argparse.Namespace) -> int:
    if ns.data_command == "export":
        return _export(ns)
    if ns.data_command == "delete":
        return _delete(ns)
    print(
        "usage: akande data {export,delete} …",
        file=sys.stderr,
    )
    return 2


def _export(ns: argparse.Namespace) -> int:
    store = ConversationStore()
    memory = MemoryStore(user_id=ns.user)
    payload = _dump_user(store, ns.user, memory=memory)
    text = json.dumps(
        payload,
        sort_keys=True,
        indent=2,
        ensure_ascii=False,
        # SQLite returns datetimes for declared TIMESTAMP columns;
        # serialise them as ISO strings rather than raising.
        default=str,
    )
    if ns.output:
        with open(ns.output, "w", encoding="utf-8") as fh:
            fh.write(text)
        print(
            f"Wrote {payload['conversation_count']} "
            f"conversations for user_id={ns.user!r} → "
            f"{ns.output}",
            file=sys.stderr,
        )
    else:
        sys.stdout.write(text)
        sys.stdout.write("\n")
    return 0


def _delete(ns: argparse.Namespace) -> int:
    store = ConversationStore()
    memory = MemoryStore(user_id=ns.user)
    conversations = store.list(user_id=ns.user, limit=10_000)
    memory_count = (
        len(memory.recall("", limit=10_000) or [])
        if memory.enabled
        else 0
    )

    if not conversations and not memory_count:
        print(
            f"No data found for user_id={ns.user!r}",
            file=sys.stderr,
        )
        return 0
    if not ns.yes:
        print(
            f"Refusing to delete {len(conversations)} "
            f"conversations and {memory_count} memories for "
            f"user_id={ns.user!r} without --yes",
            file=sys.stderr,
        )
        return 1
    for conv in conversations:
        store.delete(conv.id)
    memory_deleted = (
        memory.forget_all() if memory.enabled else 0
    )
    print(
        f"Deleted {len(conversations)} conversations and "
        f"{memory_deleted} memories for "
        f"user_id={ns.user!r}",
        file=sys.stderr,
    )
    return 0
