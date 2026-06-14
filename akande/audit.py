# Copyright (C) 2026 Sebastien Rousseau.
#
# Licensed under the Apache License, Version 2.0 (the "License").
"""Ed25519-signed audit trail for briefings.

Every briefing we generate can be paired with an audit *manifest*:
a JSON document that captures who produced it (provider + model +
schema version), the inputs and outputs (prompt hash + response
hash), the audit metadata (timestamp, profile, correlation id),
and an Ed25519 signature over the canonical form of the document.

Why JSON instead of full PDF/A-3b embedded attachments?  PDF/A-3b
gives stronger compliance posture but requires writing the
manifest as a PDF file-attachment object, which reportlab does
not expose cleanly.  v0.0.6-dev.3 ships sidecar ``.audit.json``
files alongside each briefing; v0.0.6-dev.4 will fold the
attachment into the PDF itself once the dependency choice is
settled.

Keys live in ``$AKANDE_HOME/keys/`` (default
``~/.akande/keys/``):

- ``signing.ed25519`` — private key, 0600
- ``signing.pub``     — public key,  0644

Both files are PEM-encoded.  The keypair is generated lazily on
first sign / verify call; rotation is supported by deleting the
private key and re-running.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

logger = logging.getLogger(__name__)

AUDIT_SCHEMA_VERSION = 1
AUDIT_SUFFIX = ".audit.json"


def _akande_home() -> Path:
    """Return the per-user Àkàndé state directory.

    Honours ``AKANDE_HOME`` for tests + container deployments; falls
    back to ``~/.akande``.  Created if missing.
    """
    home = os.getenv("AKANDE_HOME") or str(
        Path.home() / ".akande"
    )
    path = Path(home)
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    return path


def _keys_dir() -> Path:
    p = _akande_home() / "keys"
    p.mkdir(parents=True, exist_ok=True, mode=0o700)
    return p


def _sha256_hex(data: str | bytes) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


@dataclass
class AuditManifest:
    """Canonical, signable description of a briefing.

    The fields are deliberately small + structured so the manifest
    is greppable, diff-able, and round-trips through ``json.dumps``
    losslessly.  Anything large (the full response text) is stored
    as a SHA-256 hex digest.
    """

    schema_version: int
    created_at: str
    provider: str
    model: str
    profile: str
    prompt_hash: str
    response_hash: str
    response_chars: int
    correlation_id: str | None = None
    extras: dict[str, Any] = field(default_factory=dict)

    def to_canonical_json(self) -> bytes:
        """Encode the manifest with sorted keys for stable signing.

        Sorted keys + no whitespace make this deterministic across
        Python versions and across machines.  Signing the canonical
        form lets a verifier reconstruct the bytes exactly without
        having to preserve unrelated formatting.
        """
        return json.dumps(
            self.__dict__,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")

    def to_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)


def build_manifest(
    *,
    prompt: str,
    response: str,
    provider: str,
    model: str,
    profile: str,
    correlation_id: str | None = None,
    extras: dict[str, Any] | None = None,
) -> AuditManifest:
    """Construct a manifest from the components of a briefing."""
    return AuditManifest(
        schema_version=AUDIT_SCHEMA_VERSION,
        created_at=datetime.now(timezone.utc).isoformat(),
        provider=provider,
        model=model,
        profile=profile,
        prompt_hash=_sha256_hex(prompt),
        response_hash=_sha256_hex(response),
        response_chars=len(response),
        correlation_id=correlation_id,
        extras=extras or {},
    )


class KeyManager:
    """Load or generate the signing keypair lazily.

    A single instance is cheap (file I/O on first call, in-memory
    after) so the public API uses a module-level :func:`signer`
    helper for callers that don't care about lifetime.
    """

    PRIV_NAME = "signing.ed25519"
    PUB_NAME = "signing.pub"

    def __init__(self, keys_dir: Path | None = None) -> None:
        self.keys_dir = keys_dir or _keys_dir()
        self._priv: Ed25519PrivateKey | None = None
        self._pub: Ed25519PublicKey | None = None

    @property
    def private_key_path(self) -> Path:
        return self.keys_dir / self.PRIV_NAME

    @property
    def public_key_path(self) -> Path:
        return self.keys_dir / self.PUB_NAME

    def load_or_create(
        self,
    ) -> tuple[Ed25519PrivateKey, Ed25519PublicKey]:
        if self._priv is not None and self._pub is not None:
            return self._priv, self._pub
        priv_path = self.private_key_path
        if priv_path.is_file():
            self._priv = self._load_private(priv_path)
            self._pub = self._priv.public_key()
            return self._priv, self._pub
        # First-run: mint a fresh keypair and persist it.
        self._priv = Ed25519PrivateKey.generate()
        self._pub = self._priv.public_key()
        self._save_private(self._priv, priv_path)
        self._save_public(self._pub, self.public_key_path)
        logger.info(
            "Audit signing key generated",
            extra={
                "event": "Audit:KeyGenerated",
                "extra_data": {
                    "private_key_path": str(priv_path),
                    "public_key_path": str(
                        self.public_key_path
                    ),
                },
            },
        )
        return self._priv, self._pub

    def public_key(self) -> Ed25519PublicKey:
        _, pub = self.load_or_create()
        return pub

    @staticmethod
    def _load_private(path: Path) -> Ed25519PrivateKey:
        with path.open("rb") as fh:
            data = fh.read()
        key = serialization.load_pem_private_key(
            data, password=None
        )
        if not isinstance(key, Ed25519PrivateKey):  # pragma: no cover - non-Ed25519 file
            raise RuntimeError(
                f"key at {path} is not Ed25519"
            )
        return key

    @staticmethod
    def _save_private(
        key: Ed25519PrivateKey, path: Path
    ) -> None:
        data = key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        with path.open("wb") as fh:
            fh.write(data)
        try:
            os.chmod(path, 0o600)
        except OSError:  # pragma: no cover - filesystem-specific
            pass  # Windows or read-only mounts.

    @staticmethod
    def _save_public(
        key: Ed25519PublicKey, path: Path
    ) -> None:
        data = key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        with path.open("wb") as fh:
            fh.write(data)
        try:
            os.chmod(path, 0o644)
        except OSError:  # pragma: no cover - filesystem-specific
            pass


_default_manager: KeyManager | None = None


def _manager() -> KeyManager:
    global _default_manager
    if _default_manager is None:
        _default_manager = KeyManager()
    return _default_manager


def _reset_manager_for_tests() -> None:
    global _default_manager
    _default_manager = None


def sign_manifest(
    manifest: AuditManifest,
    manager: KeyManager | None = None,
) -> dict[str, Any]:
    """Return the manifest as a dict with appended signature block.

    The returned dict has the manifest fields plus a top-level
    ``signature`` object containing the algorithm and base64-
    encoded bytes.  The signature is computed over the canonical
    JSON of the manifest *without* the ``signature`` field, so
    verifiers can drop the signature, re-canonicalise, and check.
    """
    mgr = manager or _manager()
    priv, _ = mgr.load_or_create()
    sig = priv.sign(manifest.to_canonical_json())
    body = manifest.to_dict()
    body["signature"] = {
        "alg": "ed25519",
        "sig_b64": base64.b64encode(sig).decode("ascii"),
    }
    return body


def verify_manifest_dict(
    body: dict[str, Any],
    manager: KeyManager | None = None,
) -> bool:
    """Return ``True`` if the signed manifest verifies.

    Logs the outcome with the prompt-hash prefix so an operator
    can correlate verifier output with originating briefings
    without leaking the prompt contents.
    """
    if "signature" not in body:
        logger.warning(
            "Manifest missing signature block",
            extra={"event": "Audit:VerifyNoSignature"},
        )
        return False
    sig_block = body["signature"]
    if sig_block.get("alg") != "ed25519":
        logger.warning(
            "Unsupported signature algorithm",
            extra={
                "event": "Audit:VerifyAlgUnsupported",
                "extra_data": {"alg": sig_block.get("alg")},
            },
        )
        return False
    try:
        sig = base64.b64decode(sig_block["sig_b64"])
    except (TypeError, ValueError):
        return False
    fields = {k: v for k, v in body.items() if k != "signature"}
    manifest = AuditManifest(**fields)
    mgr = manager or _manager()
    pub = mgr.public_key()
    try:
        pub.verify(sig, manifest.to_canonical_json())
    except InvalidSignature:
        logger.warning(
            "Audit manifest signature invalid",
            extra={
                "event": "Audit:VerifyFailed",
                "extra_data": {
                    "prompt_hash_prefix": manifest.prompt_hash[
                        :12
                    ],
                },
            },
        )
        return False
    return True


def write_sidecar(
    manifest: AuditManifest,
    pdf_path: Path | str,
    manager: KeyManager | None = None,
) -> Path:
    """Write the signed manifest as ``<pdf>.audit.json`` and return the path."""
    body = sign_manifest(manifest, manager=manager)
    sidecar = Path(str(pdf_path) + AUDIT_SUFFIX)
    with sidecar.open("w", encoding="utf-8") as fh:
        json.dump(
            body,
            fh,
            sort_keys=True,
            indent=2,
            ensure_ascii=False,
        )
    try:
        os.chmod(sidecar, 0o600)
    except OSError:  # pragma: no cover - filesystem-specific
        pass
    logger.info(
        "Audit sidecar written",
        extra={
            "event": "Audit:SidecarWritten",
            "extra_data": {
                "path": str(sidecar),
                "prompt_hash_prefix": manifest.prompt_hash[:12],
                "response_chars": manifest.response_chars,
            },
        },
    )
    return sidecar


def verify_sidecar(
    sidecar_path: Path | str,
    manager: KeyManager | None = None,
) -> bool:
    """Load + verify a previously-written audit sidecar JSON."""
    with Path(sidecar_path).open("r", encoding="utf-8") as fh:
        body = json.load(fh)
    return verify_manifest_dict(body, manager=manager)
