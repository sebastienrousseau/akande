# Copyright (C) 2026 Sebastien Rousseau.
#
# Licensed under the Apache License, Version 2.0 (the "License").
"""Tests for akande.disclosure (v0.0.6 Track E)."""

from akande.disclosure import (
    DEFAULT_DISCLOSURE,
    SHORT_DISCLOSURE,
    get_disclosure_text,
    log_disclosure_emitted,
    log_disclosure_suppressed,
    should_disclose,
)
from akande.profiles import EU, INTERNAL, LOCAL


class TestText:
    def test_default_mentions_ai(self):
        assert "AI" in get_disclosure_text()

    def test_short_form(self):
        assert (
            get_disclosure_text(short=True) == SHORT_DISCLOSURE
        )

    def test_default_long_form(self):
        assert get_disclosure_text() == DEFAULT_DISCLOSURE

    def test_custom_wording_passes_through_when_compliant(self):
        out = get_disclosure_text(
            custom="You're chatting with an AI helper."
        )
        assert "AI" in out
        assert out == "You're chatting with an AI helper."

    def test_custom_without_ai_falls_back(self):
        # Falls back rather than letting a bad custom string ship.
        out = get_disclosure_text(custom="Welcome!")
        assert out == DEFAULT_DISCLOSURE


class TestShouldDisclose:
    def test_eu_profile_requires_disclosure(self):
        assert should_disclose(EU) is True

    def test_local_profile_does_not(self):
        assert should_disclose(LOCAL) is False

    def test_internal_profile_does_not(self):
        assert should_disclose(INTERNAL) is False


class TestLogHelpers:
    def test_emit_logs_at_info(self, caplog):
        with caplog.at_level("INFO"):
            log_disclosure_emitted(
                "voice", text="hello", correlation_id="abc"
            )
        assert any(
            "AI disclosure emitted" in r.message
            for r in caplog.records
        )

    def test_suppressed_logs_at_warning(self, caplog):
        with caplog.at_level("WARNING"):
            log_disclosure_suppressed(
                "voice", "internal acknowledged"
            )
        assert any(
            "AI disclosure suppressed" in r.message
            for r in caplog.records
        )
