from datetime import datetime, timedelta
from typing import Optional
import logging
import sqlite3
import threading
import time


class SQLiteCache:
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
                f"""
                    Cache {hit_miss}
                    for {prompt_hash}.
                    Access latency: {latency:.2f} ms
                """
            )
            return result[0] if result else None

    def set(self, prompt_hash: str, response: str):
        with self.lock, sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "REPLACE INTO cache (prompt_hash, response) VALUES (?, ?)",
                (prompt_hash, response),
            )
            cursor.execute(
                """
                    DELETE FROM cache
                    WHERE timestamp <= (SELECT timestamp
                    FROM cache
                    ORDER BY timestamp DESC LIMIT 1 OFFSET ?)
                """,
                (self.max_size,),
            )
            conn.commit()
