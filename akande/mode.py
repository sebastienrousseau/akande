# Copyright (C) 2026 Sebastien Rousseau.
#
# Licensed under the Apache License, Version 2.0 (the "License").
"""``AKANDE_MODE`` — the one-flag sovereignty switch.

A *mode* answers the question "may this Àkàndé instance talk to the
public internet for inference?".  It is orthogonal to the
compliance profile (:mod:`akande.profiles`): you can run
``AKANDE_PROFILE=eu`` with ``AKANDE_MODE=online`` for an
EU-residency-aware cloud setup, or ``AKANDE_MODE=offline`` for a
fully local stack regardless of profile.

Modes
-----
- ``online`` (default) — every provider in ``akande/providers/`` is
  permitted.  Matches v0.0.5 behaviour exactly.
- ``offline`` — only providers whose default endpoint is on the
  local network are permitted (``ollama``, ``lmstudio``).  Any
  attempt to load a remote provider raises
  :class:`OfflineModeViolation` so the operator sees the constraint
  immediately rather than getting a silent network call.

The check lives at the provider-registry boundary so the rest of
the codebase never has to ask "is this allowed?" — by the time a
caller has an :class:`~akande.providers.base.LLMProvider`, it has
already been vetted.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass

logger = logging.getLogger(__name__)


LOCAL_ONLY_PROVIDERS = frozenset({"ollama", "lmstudio"})


class OfflineModeViolation(RuntimeError):
    """Raised when offline mode would be broken by a network call."""


@dataclass(frozen=True)
class Mode:
    name: str
    allow_remote_providers: bool

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.name


ONLINE = Mode(name="online", allow_remote_providers=True)
OFFLINE = Mode(name="offline", allow_remote_providers=False)


def resolve_mode(name: str | None = None) -> Mode:
    """Return the active mode, defaulting to ``online``."""
    key = (name or os.getenv("AKANDE_MODE") or "online").strip().lower()
    if key == "offline":
        return OFFLINE
    if key not in {"online", ""}:
        logger.warning(
            "Unknown AKANDE_MODE %r — defaulting to online",
            key,
            extra={"event": "Mode:UnknownFallback"},
        )
    return ONLINE


def active_mode() -> Mode:
    """Resolve the mode from env on every call (no caching).

    Cheap and avoids leaking state into tests that patch env vars.
    """
    return resolve_mode()


def enforce_for_provider(provider_name: str) -> None:
    """Raise :class:`OfflineModeViolation` for non-local providers in offline mode."""
    mode = active_mode()
    if mode.allow_remote_providers:
        return
    if provider_name in LOCAL_ONLY_PROVIDERS:
        return
    raise OfflineModeViolation(
        f"AKANDE_MODE=offline forbids provider "
        f"{provider_name!r}.  Permitted local providers: "
        f"{sorted(LOCAL_ONLY_PROVIDERS)}.  Set "
        f"LLM_PROVIDER=ollama (or lmstudio), or switch to "
        f"AKANDE_MODE=online."
    )
