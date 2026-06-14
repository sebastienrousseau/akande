# Copyright (C) 2026 Sebastien Rousseau.
#
# Licensed under the Apache License, Version 2.0 (the "License").
"""Tests for akande.profiles (v0.0.6 Track E)."""

from unittest.mock import patch

import pytest

from akande.profiles import (
    EU,
    INTERNAL,
    LOCAL,
    STRICT,
    known_profiles,
    resolve_profile,
)


class TestProfileFlags:
    def test_local_is_permissive(self):
        assert LOCAL.ai_disclosure is False
        assert LOCAL.audit_signing is False
        assert LOCAL.safety_envelope is False

    def test_eu_has_full_article50_controls(self):
        assert EU.ai_disclosure is True
        assert EU.audio_watermark is True
        assert EU.audit_signing is True
        assert EU.cache_redact_pii is True
        assert EU.refuse_voice_clone_without_consent is True
        assert EU.eu_residency_hint is True
        assert EU.safety_envelope is True

    def test_strict_matches_eu_except_residency(self):
        assert STRICT.ai_disclosure is True
        assert STRICT.audit_signing is True
        assert STRICT.eu_residency_hint is False

    def test_summary_lists_active_flags(self):
        text = EU.summary()
        assert text.startswith("profile=eu")
        assert "ai_disclosure" in text


class TestKnownProfiles:
    def test_returns_all_four(self):
        assert set(known_profiles()) == {
            "local",
            "eu",
            "strict",
            "internal",
        }


class TestResolveProfile:
    def test_none_returns_local(self):
        assert resolve_profile(None) is LOCAL

    def test_empty_returns_local(self):
        assert resolve_profile("") is LOCAL

    def test_case_insensitive(self):
        assert resolve_profile("EU") is EU
        assert resolve_profile("Eu  ") is EU

    def test_unknown_falls_back_to_local(self, caplog):
        with caplog.at_level("WARNING"):
            assert resolve_profile("hypothetical") is LOCAL
        assert any(
            "Unknown AKANDE_PROFILE" in r.message
            for r in caplog.records
        )

    def test_internal_requires_ack(self, caplog):
        with patch.dict("os.environ", {}, clear=False):
            # Without AKANDE_INTERNAL_ACK, internal downgrades to strict.
            import os

            os.environ.pop("AKANDE_INTERNAL_ACK", None)
            assert resolve_profile("internal") is STRICT

    def test_internal_with_ack_activates(self):
        import os

        os.environ["AKANDE_INTERNAL_ACK"] = "1"
        try:
            assert resolve_profile("internal") is INTERNAL
        finally:
            os.environ.pop("AKANDE_INTERNAL_ACK", None)
