# Copyright (C) 2026 Sebastien Rousseau.
#
# Licensed under the Apache License, Version 2.0 (the "License").
"""Operational profiles — the user-visible way to flip several
hardening switches at once.

A *profile* is a named bundle of feature flags Àkàndé reads at
startup and exposes through :class:`Profile`.  The default profile
is permissive (``local``); the ``eu`` profile activates the EU AI
Act Article 50 controls (binding 2 August 2026) plus the
GDPR-friendly defaults that ride alongside them.

The profile is selected with the ``AKANDE_PROFILE`` environment
variable.  Anything that isn't a known profile name falls back to
``local`` with a warning, so a typo can never silently turn off
compliance controls in production.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Iterable

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Profile:
    """An immutable bundle of compliance / hardening flags.

    Attributes are intentionally boolean so callers can write
    ``if profile.ai_disclosure: ...`` without parsing strings.
    """

    name: str
    ai_disclosure: bool
    audio_watermark: bool
    audit_signing: bool
    cache_redact_pii: bool
    telemetry_opt_in: bool
    refuse_voice_clone_without_consent: bool
    eu_residency_hint: bool
    safety_envelope: bool

    def summary(self) -> str:
        flags = [
            ("ai_disclosure", self.ai_disclosure),
            ("audio_watermark", self.audio_watermark),
            ("audit_signing", self.audit_signing),
            ("cache_redact_pii", self.cache_redact_pii),
            ("telemetry_opt_in", self.telemetry_opt_in),
            (
                "refuse_voice_clone_without_consent",
                self.refuse_voice_clone_without_consent,
            ),
            ("eu_residency_hint", self.eu_residency_hint),
            ("safety_envelope", self.safety_envelope),
        ]
        on = ",".join(k for k, v in flags if v)
        return f"profile={self.name} controls={on or 'none'}"


# Permissive default for local development.  Mirrors v0.0.5 behaviour
# so existing users see no change unless they opt into a stricter
# profile.
LOCAL = Profile(
    name="local",
    ai_disclosure=False,
    audio_watermark=False,
    audit_signing=False,
    cache_redact_pii=False,
    telemetry_opt_in=False,
    refuse_voice_clone_without_consent=True,
    eu_residency_hint=False,
    safety_envelope=False,
)

# Enables Article-50 controls + GDPR-aligned defaults.  The plan in
# ~/Drop/akande-ip.md §4 (Track E) specifies the matrix this
# corresponds to; docs/compliance/eu.md is the public-facing version.
EU = Profile(
    name="eu",
    ai_disclosure=True,
    audio_watermark=True,
    audit_signing=True,
    cache_redact_pii=True,
    telemetry_opt_in=False,
    refuse_voice_clone_without_consent=True,
    eu_residency_hint=True,
    safety_envelope=True,
)

# Like ``eu`` minus residency / telemetry constraints.  For
# regulated-industry deployments outside the EU that still want
# audit-grade controls.
STRICT = Profile(
    name="strict",
    ai_disclosure=True,
    audio_watermark=True,
    audit_signing=True,
    cache_redact_pii=True,
    telemetry_opt_in=False,
    refuse_voice_clone_without_consent=True,
    eu_residency_hint=False,
    safety_envelope=True,
)

# Internal-only mode: explicitly suppresses AI-disclosure.  Allowed
# *only* with the operator acknowledging via the env var
# ``AKANDE_INTERNAL_ACK=1``.  Audit signing remains on so the
# decision is traceable.
INTERNAL = Profile(
    name="internal",
    ai_disclosure=False,
    audio_watermark=False,
    audit_signing=True,
    cache_redact_pii=True,
    telemetry_opt_in=False,
    refuse_voice_clone_without_consent=True,
    eu_residency_hint=False,
    safety_envelope=True,
)

_KNOWN: dict[str, Profile] = {
    "local": LOCAL,
    "eu": EU,
    "strict": STRICT,
    "internal": INTERNAL,
}


def known_profiles() -> Iterable[str]:
    """Return the names of all built-in profiles."""
    return list(_KNOWN.keys())


def resolve_profile(name: str | None) -> Profile:
    """Look up a profile by name with safe fallback.

    Selection rules:

    - ``None`` or empty → :data:`LOCAL` (matches existing behaviour).
    - ``"internal"`` requires ``AKANDE_INTERNAL_ACK=1`` in the
      environment; otherwise we refuse the downgrade and return
      :data:`STRICT` with a warning so the operator notices.
    - Unknown name → :data:`LOCAL` with a warning.
    """
    if not name:
        return LOCAL
    key = name.strip().lower()
    if key == "internal":
        if os.getenv("AKANDE_INTERNAL_ACK", "0") != "1":
            logger.warning(
                "AKANDE_PROFILE=internal requested without "
                "AKANDE_INTERNAL_ACK=1 — refusing the downgrade "
                "and using profile=strict instead",
                extra={
                    "event": "Profile:InternalRefused",
                },
            )
            return STRICT
        logger.warning(
            "AI disclosure is disabled (profile=internal). "
            "EU AI Act Article 50 applies to any user-facing "
            "interaction.  Restrict this profile to internal-"
            "only deployments.",
            extra={"event": "Profile:InternalActivated"},
        )
        return INTERNAL
    if key not in _KNOWN:
        logger.warning(
            "Unknown AKANDE_PROFILE %r — falling back to local",
            key,
            extra={
                "event": "Profile:UnknownFallback",
                "extra_data": {"requested": key},
            },
        )
        return LOCAL
    return _KNOWN[key]


def active_profile() -> Profile:
    """Resolve the profile from the ``AKANDE_PROFILE`` env var.

    Cached at module level under ``_active`` so repeated calls in
    the hot path are cheap.  Tests that flip the env var should
    call :func:`_reset_active_for_tests`.
    """
    global _active
    if _active is None:
        _active = resolve_profile(os.getenv("AKANDE_PROFILE"))
        logger.info(
            "Profile resolved",
            extra={
                "event": "Profile:Resolved",
                "extra_data": {
                    "summary": _active.summary(),
                },
            },
        )
    return _active


_active: Profile | None = None


def _reset_active_for_tests() -> None:
    """Clear the cached profile so the next call re-reads env."""
    global _active
    _active = None
