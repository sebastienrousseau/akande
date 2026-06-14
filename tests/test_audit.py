# Copyright (C) 2026 Sebastien Rousseau.
#
# Licensed under the Apache License, Version 2.0 (the "License").
"""Tests for akande.audit (v0.0.6 Track E)."""

import json

import pytest

from akande.audit import (
    AUDIT_SUFFIX,
    KeyManager,
    _reset_manager_for_tests,
    build_manifest,
    sign_manifest,
    verify_manifest_dict,
    verify_sidecar,
    write_sidecar,
)


@pytest.fixture
def isolated_keys(tmp_path, monkeypatch):
    monkeypatch.setenv("AKANDE_HOME", str(tmp_path))
    _reset_manager_for_tests()
    yield tmp_path
    _reset_manager_for_tests()


class TestManifestCanonicalisation:
    def test_sorts_keys(self):
        m = build_manifest(
            prompt="q",
            response="r",
            provider="openai",
            model="gpt-4o-mini",
            profile="eu",
        )
        encoded = m.to_canonical_json().decode("utf-8")
        # Sorted-keys means 'created_at' comes before 'profile'.
        assert encoded.index("created_at") < encoded.index("profile")

    def test_hashes_inputs(self):
        m = build_manifest(
            prompt="abc",
            response="xyz",
            provider="p",
            model="m",
            profile="eu",
        )
        # SHA-256 hex of 'abc' starts with 'ba78'.
        assert m.prompt_hash.startswith("ba78")
        assert len(m.prompt_hash) == 64


class TestSignAndVerify:
    def test_roundtrip(self, isolated_keys):
        m = build_manifest(
            prompt="q",
            response="r",
            provider="openai",
            model="m",
            profile="eu",
        )
        body = sign_manifest(m)
        assert "signature" in body
        assert body["signature"]["alg"] == "ed25519"
        assert verify_manifest_dict(body) is True

    def test_tamper_detected(self, isolated_keys):
        m = build_manifest(
            prompt="q",
            response="r",
            provider="openai",
            model="m",
            profile="eu",
        )
        body = sign_manifest(m)
        body["response_chars"] = body["response_chars"] + 1
        assert verify_manifest_dict(body) is False

    def test_missing_signature_block_rejected(self, isolated_keys):
        m = build_manifest(
            prompt="q",
            response="r",
            provider="p",
            model="m",
            profile="eu",
        )
        body = m.to_dict()  # no signature
        assert verify_manifest_dict(body) is False

    def test_unsupported_alg_rejected(self, isolated_keys):
        m = build_manifest(
            prompt="q",
            response="r",
            provider="p",
            model="m",
            profile="eu",
        )
        body = sign_manifest(m)
        body["signature"]["alg"] = "rsa"
        assert verify_manifest_dict(body) is False


class TestKeyManager:
    def test_first_call_mints_pair(self, isolated_keys):
        km = KeyManager()
        priv, pub = km.load_or_create()
        assert km.private_key_path.is_file()
        assert km.public_key_path.is_file()
        # Subsequent call reuses.
        priv2, pub2 = km.load_or_create()
        assert priv is priv2
        assert pub is pub2

    def test_private_key_perms_600(self, isolated_keys):
        import os

        if os.name == "nt":
            pytest.skip("Windows permissions differ")
        km = KeyManager()
        km.load_or_create()
        mode = os.stat(km.private_key_path).st_mode & 0o777
        assert mode == 0o600


class TestSidecar:
    def test_write_then_verify(self, isolated_keys, tmp_path):
        m = build_manifest(
            prompt="hello",
            response="world",
            provider="openai",
            model="gpt-4o-mini",
            profile="eu",
        )
        fake_pdf = tmp_path / "briefing.pdf"
        fake_pdf.write_bytes(b"%PDF-1.4 fake")
        sidecar = write_sidecar(m, fake_pdf)
        assert sidecar.suffix == ".json"
        assert sidecar.name.endswith(AUDIT_SUFFIX)
        assert verify_sidecar(sidecar) is True

    def test_sidecar_is_pretty_json(self, isolated_keys, tmp_path):
        m = build_manifest(
            prompt="x",
            response="y",
            provider="p",
            model="m",
            profile="eu",
        )
        fake_pdf = tmp_path / "x.pdf"
        fake_pdf.write_text("dummy")
        sidecar = write_sidecar(m, fake_pdf)
        body = json.loads(sidecar.read_text())
        assert "signature" in body
        assert isinstance(body["signature"]["sig_b64"], str)
