# Copyright (C) 2026 Sebastien Rousseau.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
"""Pluggable rate limiter with in-memory default and Redis backend.

Selected by environment:
- ``REDIS_URL`` set    → ``RedisRateLimiter`` (sliding window via ZSET).
- ``REDIS_URL`` unset  → ``InMemoryRateLimiter`` (per-process,
  thread-safe; resets on restart and is not safe across multiple
  server instances).

The factory ``build_rate_limiter`` is what the server should call; it
falls back to in-memory if ``redis`` is unavailable, logging a warning.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from typing import Optional, Protocol

logger = logging.getLogger(__name__)


class RateLimiterBackend(Protocol):
    """Common interface for rate-limit backends."""

    window: int
    max_requests: int

    def is_allowed(self, key: str) -> bool: ...


class InMemoryRateLimiter:
    """Thread-safe sliding-window limiter, per-process.

    Suitable for single-instance deployments and tests.  Not suitable
    behind a load balancer — use ``RedisRateLimiter`` instead.
    """

    def __init__(self, window: int, max_requests: int) -> None:
        self.window = window
        self.max_requests = max_requests
        self._requests: dict[str, list[float]] = {}
        self._lock = threading.Lock()
        self._call_count = 0

    def is_allowed(self, key: str) -> bool:
        now = time.time()
        cutoff = now - self.window
        with self._lock:
            self._call_count += 1
            if self._call_count % 100 == 0:
                stale = [
                    k
                    for k, ts in self._requests.items()
                    if not any(t > cutoff for t in ts)
                ]
                for k in stale:
                    del self._requests[k]

            timestamps = self._requests.get(key, [])
            timestamps = [t for t in timestamps if t > cutoff]
            if len(timestamps) >= self.max_requests:
                self._requests[key] = timestamps
                return False
            timestamps.append(now)
            self._requests[key] = timestamps
        return True

    def cleanup(self) -> None:
        """Remove stale keys with no recent requests."""
        cutoff = time.time() - self.window
        with self._lock:
            stale = [
                key
                for key, ts in self._requests.items()
                if not any(t > cutoff for t in ts)
            ]
            for key in stale:
                del self._requests[key]


class RedisRateLimiter:
    """Distributed sliding-window limiter backed by Redis.

    Uses a sorted set per key with the timestamp as both score and
    member (``ZADD``), prunes expired entries (``ZREMRANGEBYSCORE``),
    then counts current members (``ZCARD``).  All operations are issued
    in a pipeline so the round-trip cost is one network call per check.
    """

    def __init__(
        self,
        window: int,
        max_requests: int,
        redis_url: str,
        key_prefix: str = "akande:ratelimit:",
    ) -> None:
        try:
            import redis  # type: ignore[import-not-found]
        except ImportError as exc:  # pragma: no cover - import guard
            raise ImportError(
                "The 'redis' package is required for "
                "RedisRateLimiter.  Install it with: "
                "pip install akande[redis]"
            ) from exc

        self.window = window
        self.max_requests = max_requests
        self.key_prefix = key_prefix
        self._client = redis.Redis.from_url(
            redis_url, decode_responses=True
        )

    def is_allowed(self, key: str) -> bool:
        now = time.time()
        cutoff = now - self.window
        full_key = f"{self.key_prefix}{key}"
        # Token is uniquely tagged so concurrent calls don't collide
        # on the same score within the same millisecond.
        member = f"{now:.6f}:{os.getpid()}:{threading.get_ident()}"
        pipe = self._client.pipeline(transaction=True)
        pipe.zremrangebyscore(full_key, 0, cutoff)
        pipe.zadd(full_key, {member: now})
        pipe.zcard(full_key)
        pipe.expire(full_key, self.window + 1)
        _, _, count, _ = pipe.execute()
        if count > self.max_requests:
            # We already added ourselves; undo so the count is fair to
            # the next requester.
            self._client.zrem(full_key, member)
            return False
        return True


def build_rate_limiter(
    window: int,
    max_requests: int,
    redis_url: Optional[str] = None,
) -> RateLimiterBackend:
    """Construct a rate limiter, preferring Redis when configured.

    Parameters
    ----------
    window:
        Sliding window length, in seconds.
    max_requests:
        Maximum requests per key per window.
    redis_url:
        Optional Redis URL (``redis://host:port/db``).  If ``None``,
        falls back to the ``REDIS_URL`` environment variable; if that
        is also unset, returns an in-memory limiter.

    Returns
    -------
    A backend that satisfies :class:`RateLimiterBackend`.  Falls back
    to in-memory and logs a warning if Redis is requested but the
    client library is missing or the server is unreachable.
    """
    url = redis_url if redis_url is not None else os.getenv(
        "REDIS_URL"
    )
    if not url:
        return InMemoryRateLimiter(window, max_requests)

    try:
        limiter = RedisRateLimiter(window, max_requests, url)
        # Probe the connection eagerly so misconfiguration is loud.
        limiter._client.ping()
        return limiter
    except Exception as exc:
        logger.warning(
            "Falling back to in-memory rate limiter — "
            "Redis backend unavailable",
            extra={
                "event": "RateLimiter:RedisUnavailable",
                "extra_data": {
                    "error": type(exc).__name__,
                    "redis_url_hash": hash(url) & 0xFFFFFFFF,
                },
            },
        )
        return InMemoryRateLimiter(window, max_requests)
