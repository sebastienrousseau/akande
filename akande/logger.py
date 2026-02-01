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
import sys
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


def basic_config(filename: str, level: int, log_format: str) -> None:
    """
    Configure logging with both file and console handlers.

    Uses JSON structured logging for file output and a human-readable
    format for console output.

    :param filename: The name of the log file.
    :param level: The logging level.
    :param log_format: The format of the log messages (used for
        console output).
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

    # Console handler uses human-readable format
    console_formatter = logging.Formatter(log_format)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(console_formatter)
    root.addHandler(console_handler)
