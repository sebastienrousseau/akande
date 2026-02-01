# Copyright (C) 2024 Sebastien Rousseau.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
from datetime import datetime, timedelta
from typing import Any, Optional
import json
import logging
import os
import sqlite3
import threading
import time


class SQLiteCache:
    """
    A thread-safe SQLite-backed cache for storing prompt responses.

    Uses a persistent connection protected by a threading lock.

    Parameters
    ----------
    db_path : str
        The path to the SQLite database file.
    max_size : int, optional
        The maximum number of items in the cache.
    expiration : timedelta, optional
        The duration after which an item expires.
    """

    def __init__(
        self,
        db_path: str,
        max_size: int = 1000,
        expiration: timedelta = timedelta(days=7),
    ):
        self.db_path = str(db_path)
        self.max_size = max_size
        self.expiration = expiration
        self.lock = threading.Lock()
        # Persistent connection (thread-safe via self.lock)
        self.conn = sqlite3.connect(
            self.db_path, check_same_thread=False
        )
        self._initialize_cache()
        self._set_file_permissions()

    def _set_file_permissions(self):
        """Set restrictive permissions (0600) on the database file."""
        try:
            os.chmod(self.db_path, 0o600)
        except OSError:
            pass  # May fail on Windows or if file is not owned

    def _initialize_cache(self):
        """Create the cache table and indexes if they don't exist."""
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS cache (
                    prompt_hash TEXT PRIMARY KEY,
                    response TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_cache_timestamp
                ON cache(timestamp)
                """
            )
            self.conn.commit()
        logging.info(
            "Cache initialized",
            extra={
                "event": "Cache:Initialized",
                "extra_data": {
                    "db_path": self.db_path,
                    "max_size": self.max_size,
                },
            },
        )

    def get(self, prompt_hash: str) -> Optional[str]:
        """
        Retrieve a response from the cache.

        Parameters
        ----------
        prompt_hash : str
            The hash of the prompt.

        Returns
        -------
        Optional[str]
            The cached response, or None if not found/expired.
        """
        start_time = time.time()
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute(
                """
                SELECT response
                FROM cache
                WHERE prompt_hash = ?
                AND timestamp > ?
                """,
                (prompt_hash, datetime.now() - self.expiration),
            )
            result = cursor.fetchone()
        hit = result is not None
        latency = (time.time() - start_time) * 1000
        logging.info(
            f"Cache {'hit' if hit else 'miss'}",
            extra={
                "event": "Cache:Accessed",
                "extra_data": {
                    "prompt_hash": prompt_hash,
                    "hit": hit,
                    "latency_ms": round(latency, 2),
                },
            },
        )
        if result:
            return json.loads(result[0])
        return None

    def set(self, prompt_hash: str, response: Any) -> None:
        """
        Store a response in the cache.

        Parameters
        ----------
        prompt_hash : str
            The hash of the prompt.
        response : Any
            The response to store.
        """
        start_time = time.time()
        serialized_response = json.dumps(response)
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute(
                """REPLACE INTO cache (
                    prompt_hash,
                    response,
                    timestamp
                ) VALUES (?, ?, CURRENT_TIMESTAMP)""",
                (prompt_hash, serialized_response),
            )
            # Only evict when over capacity
            cursor.execute("SELECT count(*) FROM cache")
            count = cursor.fetchone()[0]
            if count > self.max_size:
                cursor.execute(
                    """
                    DELETE FROM cache
                    WHERE timestamp <= (
                        SELECT timestamp
                        FROM cache
                        ORDER BY timestamp DESC
                        LIMIT 1 OFFSET ?
                    )
                    """,
                    (self.max_size - 1,),
                )
            self.conn.commit()
        latency = (time.time() - start_time) * 1000
        logging.info(
            "Cache store",
            extra={
                "event": "Cache:Written",
                "extra_data": {
                    "prompt_hash": prompt_hash,
                    "latency_ms": round(latency, 2),
                },
            },
        )

    def close(self):
        """Close the persistent database connection."""
        with self.lock:
            if self.conn:
                self.conn.close()
                self.conn = None
