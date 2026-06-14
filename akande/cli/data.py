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
from typing import Any, Dict, List

from akande.conversation import ConversationStore


def _dump_user(
    store: ConversationStore, user_id: str
) -> Dict[str, Any]:
    """Build the JSON dump for a single data subject."""
    conversations = store.list(user_id=user_id, limit=10_000)
    out: List[Dict[str, Any]] = []
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
    return {
        "user_id": user_id,
        "conversation_count": len(out),
        "conversations": out,
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
    payload = _dump_user(store, ns.user)
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
    conversations = store.list(user_id=ns.user, limit=10_000)
    if not conversations:
        print(
            f"No conversations found for user_id={ns.user!r}",
            file=sys.stderr,
        )
        return 0
    if not ns.yes:
        print(
            f"Refusing to delete {len(conversations)} "
            f"conversations for user_id={ns.user!r} without "
            f"--yes",
            file=sys.stderr,
        )
        return 1
    for conv in conversations:
        store.delete(conv.id)
    print(
        f"Deleted {len(conversations)} conversations for "
        f"user_id={ns.user!r}",
        file=sys.stderr,
    )
    return 0
