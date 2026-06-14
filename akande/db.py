# Copyright (C) 2026 Sebastien Rousseau.
#
# Licensed under the Apache License, Version 2.0 (the "License").
"""SQLite connection + schema migration for conversations and turns.

Lives separately from ``cache.py`` so the long-lived conversation
store has its own lifecycle, indexes, and migration sequence.  The
database file is created lazily on first use under the standard
Àkàndé output directory (``~/.akande/conversations.db`` on macOS,
``~/.local/share/akande/conversations.db`` on Linux — whatever
``akande.utils.get_output_directory`` resolves to).
"""

from __future__ import annotations

import logging
import os
import sqlite3
import threading
from pathlib import Path

logger = logging.getLogger(__name__)

CONVERSATIONS_DB_NAME = "conversations.db"

# Schema version is stored in PRAGMA user_version.  Bumping this
# value triggers the matching migration on next open.  Keep migrations
# strictly additive — never destructive — so a downgrade does not
# silently lose user history.
CURRENT_SCHEMA_VERSION = 1

_SCHEMA_V1 = """
CREATE TABLE IF NOT EXISTS conversations (
    id          TEXT PRIMARY KEY,
    user_id     TEXT NOT NULL DEFAULT 'default',
    title       TEXT,
    created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_conversations_user_updated
    ON conversations(user_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS turns (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    conv_id     TEXT NOT NULL,
    role        TEXT NOT NULL CHECK(role IN ('user', 'assistant', 'system')),
    content     TEXT NOT NULL,
    ts          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    tokens      INTEGER,
    cost_usd    REAL,
    provider    TEXT,
    model       TEXT,
    FOREIGN KEY (conv_id) REFERENCES conversations(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_turns_conv_ts
    ON turns(conv_id, ts ASC);
"""


class ConversationDB:
    """Thread-safe SQLite handle for conversations + turns.

    A single connection is shared across threads (``check_same_thread
    =False``) and protected by a lock; this is appropriate for a
    single-process server.  Multi-process deployments should run with
    WAL mode (enabled here) so concurrent readers/writers don't block.
    """

    def __init__(self, db_path: str | None = None) -> None:
        if db_path is None:
            from akande.utils import get_output_directory

            directory = get_output_directory()
            db_path = str(Path(directory) / CONVERSATIONS_DB_NAME)
        self.db_path = db_path
        self.lock = threading.Lock()
        self.conn = sqlite3.connect(
            self.db_path,
            check_same_thread=False,
            isolation_level=None,  # autocommit
            detect_types=sqlite3.PARSE_DECLTYPES,
        )
        # Row factory for dict-style access.
        self.conn.row_factory = sqlite3.Row
        self._set_file_permissions()
        self._configure_pragmas()
        self._migrate()

    def _set_file_permissions(self) -> None:
        """Restrict the DB file to the owner (0600)."""
        try:
            os.chmod(self.db_path, 0o600)
        except OSError:  # pragma: no cover - filesystem-specific
            # Not fatal on Windows or read-only mounts.
            pass

    def _configure_pragmas(self) -> None:
        with self.lock:
            self.conn.execute("PRAGMA journal_mode = WAL")
            self.conn.execute("PRAGMA foreign_keys = ON")
            self.conn.execute("PRAGMA synchronous = NORMAL")

    def _migrate(self) -> None:
        """Apply pending migrations idempotently."""
        with self.lock:
            cur = self.conn.cursor()
            current = cur.execute("PRAGMA user_version").fetchone()[0]
            if current < 1:
                self.conn.executescript(_SCHEMA_V1)
            if current < CURRENT_SCHEMA_VERSION:
                self.conn.execute(
                    f"PRAGMA user_version = {CURRENT_SCHEMA_VERSION}"
                )
                logger.info(
                    "Conversation DB migrated",
                    extra={
                        "event": "ConversationDB:Migrated",
                        "extra_data": {
                            "from_version": current,
                            "to_version": CURRENT_SCHEMA_VERSION,
                        },
                    },
                )

    def close(self) -> None:
        with self.lock:
            if self.conn:
                self.conn.close()
                self.conn = None  # type: ignore[assignment]
