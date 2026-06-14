# Copyright (C) 2026 Sebastien Rousseau.
#
# Licensed under the Apache License, Version 2.0 (the "License").
"""Tests for the OpenTelemetry initialisation seam."""

from unittest.mock import patch

import pytest

from akande import telemetry


@pytest.fixture(autouse=True)
def _isolate_telemetry():
    """Reset module state before and after each test."""
    telemetry._reset_for_tests()
    yield
    telemetry._reset_for_tests()


class TestInitGating:
    def test_default_off_when_env_unset(self, monkeypatch):
        monkeypatch.delenv("AKANDE_TELEMETRY", raising=False)
        assert telemetry.init() is False
        assert telemetry.is_enabled() is False

    def test_off_when_env_zero(self, monkeypatch):
        monkeypatch.setenv("AKANDE_TELEMETRY", "0")
        assert telemetry.init() is False

    def test_off_when_profile_forbids(self, monkeypatch):
        monkeypatch.setenv("AKANDE_TELEMETRY", "1")
        from akande.profiles import EU

        with patch("akande.profiles.active_profile", return_value=EU):
            assert telemetry.init() is False
            assert telemetry.is_enabled() is False

    def test_on_when_env_set_and_profile_permits(self, monkeypatch):
        monkeypatch.setenv("AKANDE_TELEMETRY", "1")
        from akande.profiles import Profile

        permissive = Profile(
            name="dev",
            ai_disclosure=False,
            audio_watermark=False,
            audit_signing=False,
            cache_redact_pii=False,
            telemetry_opt_in=True,
            refuse_voice_clone_without_consent=True,
            eu_residency_hint=False,
            safety_envelope=False,
        )
        with patch(
            "akande.profiles.active_profile",
            return_value=permissive,
        ):
            ok = telemetry.init(force=True)
        assert ok is True
        assert telemetry.is_enabled() is True
        assert telemetry.tracer() is not None
        assert telemetry.meter() is not None


class TestSpanContext:
    def test_noop_yields_none_when_disabled(self):
        with telemetry.span("anything", k=1) as s:
            assert s is None

    def test_noop_swallows_no_exceptions(self):
        # When disabled the span context shouldn't swallow exceptions.
        with pytest.raises(ValueError):
            with telemetry.span("test"):
                raise ValueError("propagates")


class TestRecordMetric:
    def test_noop_when_disabled(self):
        # Just verify it doesn't raise.
        telemetry.record_metric("llm.latency_ms", 123.4, attr="x")
