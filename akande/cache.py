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
import re
import sqlite3
import threading
import time


# Module-level regex patterns for PII redaction.  Kept conservative
# so the cache stays useful as a cache; high-recall ML-based
# redaction is available when ``presidio-analyzer`` is installed
# (see :func:`_redact_pii`).
# Order matters: the most specific patterns run first so a less
# specific one (e.g. the 8-digit phone fallback) doesn't gobble a
# credit-card or IBAN it shouldn't have.
_REDACT_PATTERNS = [
    # Email addresses
    (
        re.compile(
            r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}"
        ),
        "[redacted:email]",
    ),
    # IBANs (country-code + check + 11–30 alphanum)
    (
        re.compile(
            r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b"
        ),
        "[redacted:iban]",
    ),
    # Credit-card-shaped 13–19-digit runs (Luhn not enforced — we
    # err toward redaction rather than miss real cards)
    (
        re.compile(r"\b(?:\d[ \-]?){13,19}\b"),
        "[redacted:cc]",
    ),
    # E.164 phone numbers and common international forms.  Runs
    # *after* the credit-card pattern so a 16-digit grouped run
    # isn't misclassified as a phone.
    (
        re.compile(
            r"(?<!\w)\+?\d[\d\s\-().]{7,}\d(?!\w)"
        ),
        "[redacted:phone]",
    ),
]


def _redact_pii(text: str) -> str:
    """Replace email/phone/IBAN/credit-card patterns with sentinels.

    Prefers ``presidio-analyzer`` when installed (higher recall on
    names, addresses, etc.) and falls back to the regex set when
    presidio isn't available.  The function is module-private so
    operators can monkey-patch it in tests without exposing it as
    public API.
    """
    try:
        from presidio_analyzer import (  # noqa: F401
            AnalyzerEngine,
        )

        analyzer = AnalyzerEngine()
        results = analyzer.analyze(
            text=text, language="en"
        )
        # Walk results in reverse so offsets stay valid as we splice.
        for r in sorted(
            results, key=lambda x: x.start, reverse=True
        ):
            text = (
                text[: r.start]
                + f"[redacted:{r.entity_type.lower()}]"
                + text[r.end:]
            )
        return text
    except ImportError:
        pass
    redacted = text
    for pat, repl in _REDACT_PATTERNS:
        redacted = pat.sub(repl, redacted)
    return redacted


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

    def _set_file_permissions(self) -> None:
        """Set restrictive permissions (0600) on the database file."""
        try:
            os.chmod(self.db_path, 0o600)
        except OSError:  # pragma: no cover - filesystem-specific
            pass  # May fail on Windows or if file is not owned

    def _initialize_cache(self) -> None:
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

        When the active profile has ``cache_redact_pii=True`` (the
        EU / strict / internal presets) the stored response is run
        through :func:`_redact_pii` first.  Redaction is regex-
        based by default; if ``presidio-analyzer`` is installed it
        is preferred for higher recall.  Either way the redaction
        is applied to the *cached* payload, not to anything sent
        to the LLM or returned to the user.

        Parameters
        ----------
        prompt_hash : str
            The hash of the prompt.
        response : Any
            The response to store.
        """
        start_time = time.time()
        # Honour the active profile's redaction setting.  Imported
        # lazily to avoid a hot-path import cycle with config /
        # logger modules.
        try:
            from akande.profiles import active_profile

            if active_profile().cache_redact_pii and isinstance(
                response, str
            ):
                response = _redact_pii(response)
        except Exception:
            # Redaction is best-effort; never block a cache write.
            logging.warning(
                "Cache PII redaction failed; storing raw",
                exc_info=True,
                extra={"event": "Cache:RedactFailed"},
            )
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

    def close(self) -> None:
        """Close the persistent database connection."""
        with self.lock:
            if self.conn:
                self.conn.close()
                self.conn = None  # type: ignore[assignment]
