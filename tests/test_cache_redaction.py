# Copyright (C) 2026 Sebastien Rousseau.
#
# Licensed under the Apache License, Version 2.0 (the "License").
"""Tests for the v0.0.6 cache PII redaction (Track E)."""

from unittest.mock import patch

from akande.cache import SQLiteCache, _redact_pii


class TestRedactRegex:
    def test_redacts_email(self):
        out = _redact_pii(
            "Email me at alice@example.com please"
        )
        assert "alice@example.com" not in out
        assert "[redacted:email]" in out

    def test_redacts_phone(self):
        out = _redact_pii(
            "Call me on +44 20 7946 0958 tomorrow"
        )
        assert "0958" not in out
        assert "[redacted:phone]" in out

    def test_redacts_credit_card(self):
        out = _redact_pii(
            "card 4111 1111 1111 1111 charge"
        )
        assert "4111" not in out
        assert "[redacted:cc]" in out

    def test_redacts_iban(self):
        out = _redact_pii(
            "Wire to GB29NWBK60161331926819 by EOD"
        )
        assert "GB29" not in out
        assert "[redacted:iban]" in out

    def test_passes_clean_text(self):
        text = "Just a briefing about quantitative easing."
        assert _redact_pii(text) == text


class TestProfileGating:
    def test_local_profile_does_not_redact(
        self, tmp_path
    ):
        cache = SQLiteCache(str(tmp_path / "local.db"))
        try:
            with patch(
                "akande.profiles.active_profile"
            ) as ap:
                from akande.profiles import LOCAL

                ap.return_value = LOCAL
                cache.set(
                    "h1",
                    "email me at user@example.com",
                )
            stored = cache.get("h1")
            assert "user@example.com" in (stored or "")
        finally:
            cache.close()

    def test_eu_profile_redacts(self, tmp_path):
        cache = SQLiteCache(str(tmp_path / "eu.db"))
        try:
            with patch(
                "akande.profiles.active_profile"
            ) as ap:
                from akande.profiles import EU

                ap.return_value = EU
                cache.set(
                    "h2",
                    "email me at user@example.com",
                )
            stored = cache.get("h2")
            assert "user@example.com" not in (stored or "")
            assert "[redacted:email]" in (stored or "")
        finally:
            cache.close()

    def test_redact_failure_is_swallowed(self, tmp_path):
        cache = SQLiteCache(str(tmp_path / "fail.db"))
        try:
            with patch(
                "akande.profiles.active_profile",
                side_effect=RuntimeError("boom"),
            ):
                # Must not raise — redaction is best-effort.
                cache.set("h3", "anything")
            assert cache.get("h3") == "anything"
        finally:
            cache.close()
