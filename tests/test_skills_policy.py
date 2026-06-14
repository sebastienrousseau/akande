# Copyright (C) 2026 Sebastien Rousseau.
#
# Licensed under the Apache License, Version 2.0 (the "License").
"""Tests for the persistent skill consent policy."""

import json

import pytest

from akande.skills.policy import (
    ConsentRequired,
    SkillPolicy,
)


class TestEnableDisable:
    def test_default_is_enabled(self, tmp_path):
        p = SkillPolicy(tmp_path / "policy.json")
        assert p.is_enabled("anything")

    def test_disable_persists(self, tmp_path):
        path = tmp_path / "policy.json"
        SkillPolicy(path).disable("weather")
        # New instance reads from disk.
        assert SkillPolicy(path).is_enabled("weather") is False

    def test_enable_undoes_disable(self, tmp_path):
        path = tmp_path / "policy.json"
        p = SkillPolicy(path)
        p.disable("weather")
        p.enable("weather")
        assert SkillPolicy(path).is_enabled("weather")


class TestConsent:
    def test_default_not_consented(self, tmp_path):
        p = SkillPolicy(tmp_path / "policy.json")
        assert not p.is_consented("anything")

    def test_grant_persists(self, tmp_path):
        path = tmp_path / "policy.json"
        SkillPolicy(path).grant_consent("finance")
        assert SkillPolicy(path).is_consented("finance")

    def test_revoke_undoes_grant(self, tmp_path):
        path = tmp_path / "policy.json"
        p = SkillPolicy(path)
        p.grant_consent("finance")
        p.revoke_consent("finance")
        assert not SkillPolicy(path).is_consented("finance")

    def test_require_consent_noop_when_not_required(
        self, tmp_path
    ):
        SkillPolicy(tmp_path / "policy.json").require_consent(
            "weather", requires_consent=False
        )

    def test_require_consent_raises_when_missing(
        self, tmp_path
    ):
        p = SkillPolicy(tmp_path / "policy.json")
        with pytest.raises(ConsentRequired):
            p.require_consent(
                "voice_clone", requires_consent=True
            )

    def test_require_consent_passes_after_grant(
        self, tmp_path
    ):
        p = SkillPolicy(tmp_path / "policy.json")
        p.grant_consent("voice_clone")
        p.require_consent(
            "voice_clone", requires_consent=True
        )


class TestFileShape:
    def test_persists_pretty_json(self, tmp_path):
        path = tmp_path / "policy.json"
        p = SkillPolicy(path)
        p.disable("weather")
        p.grant_consent("finance")
        body = json.loads(path.read_text())
        assert body["skills"]["weather"]["enabled"] is False
        assert (
            body["skills"]["finance"]["consented_at"]
            is not None
        )
        assert "updated_at" in body

    def test_malformed_existing_file_is_ignored(
        self, tmp_path, caplog
    ):
        path = tmp_path / "policy.json"
        path.write_text("not json")
        with caplog.at_level("WARNING"):
            p = SkillPolicy(path)
        assert p.is_enabled("anything")
