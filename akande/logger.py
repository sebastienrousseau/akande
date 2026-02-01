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
import json
import logging
import math
import sys
import threading
import traceback
from datetime import datetime, timezone


class JSONFormatter(logging.Formatter):
    """Structured JSON log formatter with mandatory context fields."""

    def __init__(self, service: str = "akande"):
        super().__init__()
        self.service = service

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "service": self.service,
            "message": record.getMessage(),
        }
        # Include correlation_id if set on the record
        correlation_id = getattr(record, "correlation_id", None)
        if correlation_id:
            log_entry["correlation_id"] = correlation_id

        # Include event name if set on the record
        event = getattr(record, "event", None)
        if event:
            log_entry["event"] = event

        # Include extra data if set on the record
        extra_data = getattr(record, "extra_data", None)
        if extra_data and isinstance(extra_data, dict):
            log_entry["data"] = extra_data

        if record.exc_info and record.exc_info[0] is not None:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": traceback.format_exception(
                    *record.exc_info
                ),
            }
        return json.dumps(log_entry, default=str)


def basic_config(
    filename: str,
    level: int,
    log_format: str,
    console: bool = True,
) -> None:
    """
    Configure logging with file and optional console handlers.

    Uses JSON structured logging for file output and a human-readable
    format for console output.

    :param filename: The name of the log file.
    :param level: The logging level.
    :param log_format: The format of the log messages (used for
        console output).
    :param console: Whether to add a console (stdout) handler.
        Set to False when running inside a TUI to prevent log
        lines from corrupting the display.
    :return: None
    """
    root = logging.getLogger()
    root.setLevel(level)

    # Remove any existing handlers to avoid duplicates
    for handler in root.handlers[:]:
        root.removeHandler(handler)

    # File handler uses JSON structured logging
    json_formatter = JSONFormatter(service="akande")
    file_handler = logging.FileHandler(filename)
    file_handler.setLevel(level)
    file_handler.setFormatter(json_formatter)
    root.addHandler(file_handler)

    if console:
        # Console handler uses human-readable format
        console_formatter = logging.Formatter(log_format)
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(console_formatter)
        root.addHandler(console_handler)


class MetricsCollector:
    """Thread-safe collector for pipeline stage latencies.

    Each stage (e.g. ``"tts"``, ``"llm"``) accumulates a list of
    latency samples in milliseconds.  The :meth:`summary` method
    returns per-stage statistics (count, mean, p95, max).
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._data: dict[str, list[float]] = {}

    def record(self, stage: str, latency_ms: float) -> None:
        """Record a latency sample for *stage*."""
        with self._lock:
            self._data.setdefault(stage, []).append(
                latency_ms
            )

    def summary(self) -> dict[str, dict[str, float]]:
        """Return per-stage statistics.

        Returns a dict mapping stage names to dicts with keys
        ``count``, ``mean``, ``p95``, and ``max``.
        """
        with self._lock:
            result: dict[str, dict[str, float]] = {}
            for stage, samples in self._data.items():
                if not samples:
                    continue
                sorted_s = sorted(samples)
                count = len(sorted_s)
                mean = sum(sorted_s) / count
                p95_idx = min(
                    math.ceil(count * 0.95) - 1,
                    count - 1,
                )
                result[stage] = {
                    "count": count,
                    "mean": round(mean, 2),
                    "p95": round(sorted_s[p95_idx], 2),
                    "max": round(sorted_s[-1], 2),
                }
            return result

    def reset(self) -> None:
        """Clear all recorded data."""
        with self._lock:
            self._data.clear()
