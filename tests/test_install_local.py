# Copyright (C) 2026 Sebastien Rousseau.
#
# Licensed under the Apache License, Version 2.0 (the "License").
"""Tests for the install-local CLI."""

import argparse
from pathlib import Path
from unittest.mock import patch

import pytest

from akande.cli.install_local import (
    OFFLINE_ENV_DEFAULTS,
    _load_env,
    _write_env,
    install_local_command,
)


class TestLoadEnv:
    def test_missing_file_returns_empty(self, tmp_path):
        assert _load_env(tmp_path / "nope") == {}

    def test_parses_keys(self, tmp_path):
        p = tmp_path / ".env"
        p.write_text("FOO=bar\nBAZ=qux\n# comment\n")
        assert _load_env(p) == {"FOO": "bar", "BAZ": "qux"}


class TestWriteEnv:
    def test_creates_with_defaults(self, tmp_path):
        target = tmp_path / "subdir" / ".env"
        _write_env(target, dry_run=False, model="llama3.1")
        body = target.read_text()
        for key in OFFLINE_ENV_DEFAULTS:
            assert f"{key}=" in body
        # 0600 perms applied where supported.
        assert (target.stat().st_mode & 0o777) == 0o600

    def test_preserves_existing_values(self, tmp_path):
        target = tmp_path / ".env"
        target.write_text(
            "OPENAI_DEFAULT_MODEL=mistral-large-latest\n"
            "OTHER=value\n"
        )
        _write_env(target, dry_run=False, model="llama3.1")
        body = target.read_text()
        # Existing override wins.
        assert "OPENAI_DEFAULT_MODEL=mistral-large-latest" in body
        # Defaults still merged.
        assert "AKANDE_MODE=offline" in body
        # Unrelated keys preserved.
        assert "OTHER=value" in body

    def test_dry_run_does_not_write(self, tmp_path):
        target = tmp_path / ".env"
        _write_env(target, dry_run=True, model="llama3.1")
        assert not target.exists()


class TestCommand:
    def _ns(self, **overrides):
        defaults = {
            "model": "llama3.1",
            "env_path": "/tmp/test.env",
            "dry_run": True,
        }
        defaults.update(overrides)
        return argparse.Namespace(**defaults)

    def test_missing_ollama_fails_cleanly(
        self, capsys, monkeypatch
    ):
        with patch(
            "akande.cli.install_local.shutil.which",
            return_value=None,
        ):
            rc = install_local_command(self._ns())
        assert rc == 1
        err = capsys.readouterr().err
        assert "ollama" in err

    def test_dry_run_path(self, tmp_path, capsys):
        env_target = tmp_path / ".env"
        with patch(
            "akande.cli.install_local.shutil.which",
            return_value="/usr/local/bin/ollama",
        ):
            rc = install_local_command(
                self._ns(env_path=str(env_target))
            )
        assert rc == 0
        # Dry-run skipped pull + pip + write.
        assert not env_target.exists()
