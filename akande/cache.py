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
from typing import Optional
import logging
import sqlite3
import threading
import time
import json


class SQLiteCache:
    """
    A simple in-memory cache for storing code completion responses.

    Parameters
    ----------
    db_path : str
        The path to the SQLite database file.
    max_size : int, optional
        The maximum size of the cache, in number of items.
    expiration : timedelta, optional
        The duration after which an item expires from the cache,
        represented as a timedelta object.

    Attributes
    ----------
    db_path : str
        The path to the SQLite database file.
    max_size : int
        The maximum size of the cache, in number of items.
    expiration : timedelta
        The duration after which an item expires from the cache,
        represented as a timedelta object.
    lock : threading.Lock
        A lock for thread-safe access to the cache.
    """

    def __init__(
        self,
        db_path: str,
        max_size: int = 1000,
        expiration: timedelta = timedelta(days=7),
    ):
        self.db_path = db_path
        self.max_size = max_size
        self.expiration = expiration
        self.lock = threading.Lock()
        self.initialize_cache()

    def initialize_cache(self):
        """
        Initialize the cache by creating the underlying SQLite database table,
        if it does not already exist.
        """
        with self.lock, sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS cache (
                    prompt_hash TEXT PRIMARY KEY,
                    response TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.commit()

    def get(self, prompt_hash: str) -> Optional[str]:
        """
        Retrieve a response from the cache.

        Parameters
        ----------
        prompt_hash : str
            The hash of the code completion prompt.

        Returns
        -------
        Optional[str]
            The cached response, if available, or None if the response is not
            in the cache or has expired.
        """
        start_time = time.time()
        with self.lock, sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
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
            hit_miss = "hit" if result else "miss"
            latency = (
                time.time() - start_time
            ) * 1000  # Convert to milliseconds
            logging.info(
                f"Cache {hit_miss} for {prompt_hash}. "
                f"Access latency: {latency:.2f} ms."
            )
            if result:
                # Deserialize the response back into a Python object
                return json.loads(result[0])
            return None

    def set(self, prompt_hash: str, response: any):
        """
        Store a response in the cache.

        Parameters
        ----------
        prompt_hash : str
            The hash of the code completion prompt.
        response : any
            The response to store in the cache.
        """
        # Serialize the response object to a JSON string
        serialized_response = json.dumps(response)
        with self.lock, sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """REPLACE INTO cache (
                    prompt_hash,
                    response,
                    timestamp
                ) VALUES (?, ?, CURRENT_TIMESTAMP)""",
                (prompt_hash, serialized_response),
            )
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
            conn.commit()
