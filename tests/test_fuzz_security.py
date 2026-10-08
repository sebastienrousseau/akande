# Copyright (C) 2026 Sebastien Rousseau.
#
# Licensed under the Apache License, Version 2.0 (the "License").
"""Property-based fuzz testing for security boundaries.

Targets:
1. Rate limiter burst edge cases and sliding-window invariants.
2. Cryptographic key serialization boundaries and signature tamper resistance.
3. Session recovery and concurrent conversation store race conditions.
"""

from __future__ import annotations

import base64
import tempfile
import threading
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from akande.audit import (
    KeyManager,
    build_manifest,
    sign_manifest,
    verify_manifest_dict,
)
from akande.conversation import ConversationStore
from akande.db import ConversationDB
from akande.server.rate_limit import InMemoryRateLimiter


class TestRateLimiterPropertyFuzzing:
    """Property-based fuzzing of rate limiter burst and boundary edge cases."""

    @given(
        window=st.integers(min_value=1, max_value=300),
        max_requests=st.integers(min_value=1, max_value=100),
        burst_size=st.integers(min_value=1, max_value=250),
    )
    @settings(max_examples=50, deadline=None)
    def test_instantaneous_burst_invariants(
        self, window: int, max_requests: int, burst_size: int
    ) -> None:
        """Any burst of requests at timestamp T admits min(burst, max_requests)."""
        limiter = InMemoryRateLimiter(
            window=window, max_requests=max_requests
        )
        results = [
            limiter.is_allowed("client-1") for _ in range(burst_size)
        ]
        allowed_count = sum(results)
        expected_allowed = min(burst_size, max_requests)

        assert allowed_count == expected_allowed
        # First min(burst_size, max_requests) must be True
        assert all(results[:expected_allowed])
        # Remaining must be False
        assert not any(results[expected_allowed:])

    @given(
        window=st.integers(min_value=2, max_value=100),
        max_requests=st.integers(min_value=1, max_value=50),
        delta=st.floats(min_value=0.01, max_value=10.0),
    )
    @settings(max_examples=40, deadline=None)
    def test_sliding_window_recovery_property(
        self, window: int, max_requests: int, delta: float
    ) -> None:
        """After window exhaustion, time advancement restores full capacity."""
        limiter = InMemoryRateLimiter(
            window=window, max_requests=max_requests
        )
        current_time = 1_000_000.0

        with patch("time.time", side_effect=lambda: current_time):
            # Exhaust capacity
            for _ in range(max_requests):
                assert limiter.is_allowed("client-rec") is True
            assert limiter.is_allowed("client-rec") is False

        # Advance time beyond the sliding window
        current_time += float(window) + delta

        with patch("time.time", side_effect=lambda: current_time):
            # Should have recovered capacity
            assert limiter.is_allowed("client-rec") is True

    @given(
        client_a=st.text(min_size=1, max_size=32),
        client_b=st.text(min_size=1, max_size=32),
        max_requests=st.integers(min_value=1, max_value=20),
    )
    @settings(max_examples=30, deadline=None)
    def test_multi_client_burst_isolation(
        self, client_a: str, client_b: str, max_requests: int
    ) -> None:
        """Bursts on client A never starve or block client B."""
        if client_a == client_b:
            client_b = client_b + "_other"

        limiter = InMemoryRateLimiter(
            window=60, max_requests=max_requests
        )
        # Exhaust client A
        for _ in range(max_requests + 10):
            limiter.is_allowed(client_a)

        assert limiter.is_allowed(client_a) is False
        # Client B must remain unaffected
        assert limiter.is_allowed(client_b) is True

    def test_concurrent_burst_race_conditions(self) -> None:
        """Concurrent multi-threaded bursts strictly observe max_requests limit."""
        max_requests = 40
        num_threads = 10
        requests_per_thread = 15  # Total 150 requests > 40 max
        limiter = InMemoryRateLimiter(
            window=60, max_requests=max_requests
        )

        barrier = threading.Barrier(num_threads)
        results: list[bool] = []
        lock = threading.Lock()

        def worker() -> None:
            barrier.wait(timeout=5.0)
            thread_results = [
                limiter.is_allowed("race-client")
                for _ in range(requests_per_thread)
            ]
            with lock:
                results.extend(thread_results)

        threads = [
            threading.Thread(target=worker) for _ in range(num_threads)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10.0)

        assert len(results) == num_threads * requests_per_thread
        assert sum(results) == max_requests

    def test_stale_client_cleanup_on_hundredth_call(self) -> None:
        """Every 100 calls, stale client entries older than window are purged."""
        limiter = InMemoryRateLimiter(window=10, max_requests=50)
        # Register a stale key at timestamp 100.0
        with patch("time.time", return_value=100.0):
            assert limiter.is_allowed("stale-client") is True
        assert "stale-client" in limiter._requests

        # At timestamp 200.0, execute 100 requests to trigger cleanup
        with patch("time.time", return_value=200.0):
            for i in range(100):
                limiter.is_allowed(f"active-client-{i}")

        # Stale key must have been deleted
        assert "stale-client" not in limiter._requests


class TestCryptographicBoundaryFuzzing:
    """Property-based fuzzing of key serialization boundaries and signature validation."""

    @given(fuzz_data=st.binary(min_size=0, max_size=4096))
    @settings(max_examples=40, deadline=None)
    def test_private_key_fuzz_deserialization_boundaries(
        self, fuzz_data: bytes
    ) -> None:
        """Malformed or random bytes never cause unhandled crashes during key load."""
        with tempfile.TemporaryDirectory() as td:
            key_file = Path(td) / "fuzz.key"
            key_file.write_bytes(fuzz_data)

            # Loading malformed private keys must cleanly raise expected exceptions
            with pytest.raises(
                (ValueError, TypeError, RuntimeError, Exception)
            ):
                KeyManager._load_private(key_file)

    @given(
        tampered_field=st.sampled_from(
            [
                "prompt_hash",
                "response_hash",
                "model",
                "provider",
                "created_at",
            ]
        ),
        corruption=st.text(min_size=1, max_size=128),
    )
    @settings(max_examples=40, deadline=None)
    def test_manifest_signature_tamper_boundaries(
        self, tampered_field: str, corruption: str
    ) -> None:
        """Any field modification in a signed manifest invalidates verification."""
        with tempfile.TemporaryDirectory() as td:
            km = KeyManager(keys_dir=Path(td))
            manifest = build_manifest(
                prompt="fuzz-prompt",
                response="fuzz-response",
                provider="openai",
                model="gpt-4o",
                profile="eu",
            )
            signed = sign_manifest(manifest, manager=km)
            assert verify_manifest_dict(signed, manager=km) is True

            # Mutate the target field
            mutated = dict(signed)
            mutated[tampered_field] = (
                str(mutated.get(tampered_field, "")) + corruption
            )

            # Verification must fail cleanly without crashing
            assert verify_manifest_dict(mutated, manager=km) is False

    @given(corrupted_b64=st.binary(min_size=1, max_size=256))
    @settings(max_examples=30, deadline=None)
    def test_corrupted_signature_payload_boundaries(
        self, corrupted_b64: bytes
    ) -> None:
        """Corrupted signature blocks are safely rejected without exception leakage."""
        with tempfile.TemporaryDirectory() as td:
            km = KeyManager(keys_dir=Path(td))
            manifest = build_manifest(
                prompt="test",
                response="test",
                provider="p",
                model="m",
                profile="eu",
            )
            signed = sign_manifest(manifest, manager=km)
            mutated = dict(signed)
            mutated["signature"] = {
                "alg": "ed25519",
                "sig_b64": base64.b64encode(corrupted_b64).decode(
                    "ascii"
                ),
            }
            assert verify_manifest_dict(mutated, manager=km) is False


class TestSessionRecoveryRaceConditions:
    """Fuzzing and race-condition validation for conversation session recovery."""

    def test_concurrent_session_turn_appending(self) -> None:
        """High-concurrency appending to a single session preserves history integrity."""
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "sessions.db"
            db = ConversationDB(db_path=db_path)
            store = ConversationStore(db=db)
            conv = store.get_or_create(None)
            num_threads = 8
            turns_per_thread = 15

            barrier = threading.Barrier(num_threads)
            errors: list[str] = []

            def worker(thread_idx: int) -> None:
                try:
                    barrier.wait(timeout=5.0)
                    for turn_idx in range(turns_per_thread):
                        store.append_turn(
                            conv.id,
                            role="user"
                            if turn_idx % 2 == 0
                            else "assistant",
                            content=f"thread-{thread_idx}-turn-{turn_idx}",
                        )
                except Exception as exc:
                    errors.append(f"Thread {thread_idx} failed: {exc}")

            threads = [
                threading.Thread(target=worker, args=(i,))
                for i in range(num_threads)
            ]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=10.0)

            assert errors == [], (
                f"Concurrency errors occurred: {errors}"
            )
            history = store.recent_turns(
                conv.id, limit=num_threads * turns_per_thread + 10
            )
            assert len(history) == num_threads * turns_per_thread
            db.close()

    @given(fuzz_id=st.text(min_size=0, max_size=256))
    @settings(max_examples=30, deadline=None)
    def test_session_recovery_boundary_inputs(
        self, fuzz_id: str
    ) -> None:
        """Arbitrary session ID inputs do not crash or leak internal database state."""
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "fuzz_conv.db"
            db = ConversationDB(db_path=db_path)
            store = ConversationStore(db=db)
            conv = store.get_or_create(
                conv_id=fuzz_id if fuzz_id else None
            )
            assert conv.id is not None
            assert isinstance(conv.id, str)
            db.close()

    def test_conversation_fetch_vanished_raises(self) -> None:
        """When conversation vanishes after insertion, RuntimeError is raised."""
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "test.db"
            db = ConversationDB(db_path=db_path)
            store = ConversationStore(db=db)
            with patch.object(store, "get", return_value=None):
                with pytest.raises(
                    RuntimeError, match="vanished after insert"
                ):
                    store._fetch_conversation("nonexistent-conv")
            db.close()


class TestToolBoundaryHandling:
    """Validate boundary condition handling for tool execution."""

    def test_execute_tool_call_tool_error_handled(self) -> None:
        """When a tool raises ToolError, execution returns an event with error."""
        from akande.tools.base import Tool, ToolError, ToolRegistry
        from akande.tools.calling import _dispatch

        class FailingTool(Tool):
            name = "fail_tool"
            description = "simulated failing tool"

            @property
            def input_schema(self) -> dict[str, Any]:
                return {}

            def run(self, args: dict[str, Any]) -> Any:
                raise ToolError("simulated tool failure")

        reg = ToolRegistry()
        reg.register(FailingTool())
        event = _dispatch(
            {"function": {"name": "fail_tool", "arguments": "{}"}}, reg
        )
        assert event.error == "simulated tool failure"
        assert event.result_content == ""
