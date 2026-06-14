# Copyright (C) 2026 Sebastien Rousseau.
#
# Licensed under the Apache License, Version 2.0 (the "License").
"""Tests for the v0.0.6 API-key auth + pluggable rate limiter."""

from unittest.mock import MagicMock, patch

import cherrypy
import pytest

from akande.server.rate_limit import (
    InMemoryRateLimiter,
    build_rate_limiter,
)


class TestBuildRateLimiter:
    def test_no_redis_url_returns_in_memory(self):
        limiter = build_rate_limiter(
            window=60, max_requests=5, redis_url=None
        )
        assert isinstance(limiter, InMemoryRateLimiter)
        assert limiter.window == 60
        assert limiter.max_requests == 5

    def test_redis_unreachable_falls_back_to_in_memory(self):
        # Point at a host that won't respond; factory must not raise.
        limiter = build_rate_limiter(
            window=60,
            max_requests=5,
            redis_url="redis://127.0.0.1:1/0",
        )
        assert isinstance(limiter, InMemoryRateLimiter)

    def test_in_memory_allows_within_limit_and_blocks_after(
        self,
    ):
        limiter = build_rate_limiter(
            window=60, max_requests=2, redis_url=None
        )
        assert limiter.is_allowed("k") is True
        assert limiter.is_allowed("k") is True
        assert limiter.is_allowed("k") is False

    def test_in_memory_separate_keys_are_independent(self):
        limiter = build_rate_limiter(
            window=60, max_requests=1, redis_url=None
        )
        assert limiter.is_allowed("a") is True
        assert limiter.is_allowed("b") is True
        assert limiter.is_allowed("a") is False


class TestApiKeyCheck:
    """``_check_api_key`` should be a no-op when ``AKANDE_API_KEY`` is
    unset, and 401-with-empty-body when set and the request header
    does not match.
    """

    @staticmethod
    def _make_server():
        from akande.server.server import AkandeServer

        with (
            patch(
                "akande.server.server.validate_api_key",
                return_value=True,
            ),
            patch("akande.server.server.OpenAIImpl"),
        ):
            return AkandeServer()

    def test_noop_when_env_key_unset(self):
        with patch("akande.server.server.AKANDE_API_KEY", None):
            server = self._make_server()
            request = MagicMock()
            request.headers = {}
            with patch.object(cherrypy, "request", request):
                # Must not raise.
                server._check_api_key()

    def test_rejects_missing_header_when_key_set(self):
        with patch("akande.server.server.AKANDE_API_KEY", "expected"):
            server = self._make_server()
            request = MagicMock()
            request.headers = {}
            request.remote.ip = "10.0.0.1"
            request.path_info = "/process_question"
            with patch.object(cherrypy, "request", request):
                with pytest.raises(cherrypy.HTTPError) as exc:
                    server._check_api_key()
                assert exc.value.status == 401

    def test_rejects_wrong_header_when_key_set(self):
        with patch("akande.server.server.AKANDE_API_KEY", "expected"):
            server = self._make_server()
            request = MagicMock()
            request.headers = {"X-Akande-Key": "wrong"}
            request.remote.ip = "10.0.0.2"
            request.path_info = "/process_question"
            with patch.object(cherrypy, "request", request):
                with pytest.raises(cherrypy.HTTPError) as exc:
                    server._check_api_key()
                assert exc.value.status == 401

    def test_allows_matching_header_when_key_set(self):
        with patch("akande.server.server.AKANDE_API_KEY", "expected"):
            server = self._make_server()
            request = MagicMock()
            request.headers = {"X-Akande-Key": "expected"}
            with patch.object(cherrypy, "request", request):
                # Must not raise.
                server._check_api_key()
