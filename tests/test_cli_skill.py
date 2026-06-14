# Copyright (C) 2026 Sebastien Rousseau.
#
# Licensed under the Apache License, Version 2.0 (the "License").
"""Tests for the akande skill CLI subcommand."""

import argparse
import json

import pytest

from akande.cli.skill import skill_command
from akande.skills.policy import SkillPolicy


@pytest.fixture
def isolated_home(tmp_path, monkeypatch):
    monkeypatch.setenv("AKANDE_HOME", str(tmp_path))
    yield tmp_path


def _ns(**overrides):
    defaults = {
        "skill_command": "list",
        "name": "",
    }
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


class TestList:
    def test_lists_built_ins(self, isolated_home, capsys):
        rc = skill_command(_ns(skill_command="list"))
        assert rc == 0
        out = capsys.readouterr().out
        body = json.loads(out)
        names = {row["name"] for row in body}
        assert {
            "briefing",
            "web_search",
            "weather",
            "finance",
        }.issubset(names)
        for row in body:
            assert "enabled" in row
            assert "consented" in row


class TestEnableDisable:
    def test_disable_then_enable_persists(
        self, isolated_home, capsys
    ):
        rc = skill_command(
            _ns(skill_command="disable", name="weather")
        )
        assert rc == 0
        assert not SkillPolicy().is_enabled("weather")
        rc = skill_command(
            _ns(skill_command="enable", name="weather")
        )
        assert rc == 0
        assert SkillPolicy().is_enabled("weather")

    def test_unknown_skill_exits_2(
        self, isolated_home, capsys
    ):
        with pytest.raises(SystemExit) as exc:
            skill_command(
                _ns(
                    skill_command="disable",
                    name="not-real",
                )
            )
        assert exc.value.code == 2


class TestConsent:
    def test_grant_and_revoke(self, isolated_home, capsys):
        rc = skill_command(
            _ns(skill_command="consent", name="finance")
        )
        assert rc == 0
        assert SkillPolicy().is_consented("finance")
        rc = skill_command(
            _ns(skill_command="revoke", name="finance")
        )
        assert rc == 0
        assert not SkillPolicy().is_consented("finance")


class TestUnknownSubcommand:
    def test_returns_usage_exit(self, capsys):
        rc = skill_command(_ns(skill_command="bogus"))
        assert rc == 2
