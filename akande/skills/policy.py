# Copyright (C) 2026 Sebastien Rousseau.
#
# Licensed under the Apache License, Version 2.0 (the "License").
"""Per-skill consent + enable/disable persistence.

State lives at ``$AKANDE_HOME/skills/policy.json`` (default
``~/.akande/skills/policy.json``).  The file is small and
human-readable so operators can audit / mutate it without going
through the CLI when they need to.

Shape::

    {
      "skills": {
        "weather":   {"enabled": true,  "consented_at": "2026-06-14T10:11:00Z"},
        "finance":   {"enabled": true,  "consented_at": null},
        "web_search":{"enabled": false, "consented_at": "..."}
      },
      "updated_at": "2026-06-14T10:11:30Z"
    }

A skill's consent state defaults to "not consented"; the runtime
raises :class:`ConsentRequired` when a skill with
``requires_consent=True`` is invoked without a recorded consent.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

POLICY_FILE_NAME = "policy.json"


class ConsentRequired(RuntimeError):
    """Raised when a consent-gated skill is invoked without consent."""


def _akande_home() -> Path:
    home = os.getenv("AKANDE_HOME") or str(Path.home() / ".akande")
    path = Path(home)
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    return path


def _policy_dir() -> Path:
    p = _akande_home() / "skills"
    p.mkdir(parents=True, exist_ok=True, mode=0o700)
    return p


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class SkillPolicy:
    """Persistent per-skill enable / consent state."""

    def __init__(self, policy_path: Path | None = None) -> None:
        self.policy_path = policy_path or (
            _policy_dir() / POLICY_FILE_NAME
        )
        self._state: dict[str, dict[str, Any]] = {}
        self._load()

    # -- I/O ----------------------------------------------------

    def _load(self) -> None:
        if not self.policy_path.is_file():
            return
        try:
            raw = json.loads(
                self.policy_path.read_text(encoding="utf-8")
            )
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning(
                "Failed to read skill policy: %s",
                exc,
                extra={"event": "Skill:PolicyReadFailed"},
            )
            return
        skills = raw.get("skills") or {}
        if not isinstance(skills, dict):
            return
        for name, entry in skills.items():
            if not isinstance(entry, dict):
                continue
            self._state[name] = {
                "enabled": bool(entry.get("enabled", True)),
                "consented_at": (
                    entry.get("consented_at")
                    if isinstance(entry.get("consented_at"), str)
                    else None
                ),
            }

    def _save(self) -> None:
        payload = {
            "skills": {
                name: {
                    "enabled": entry["enabled"],
                    "consented_at": entry["consented_at"],
                }
                for name, entry in self._state.items()
            },
            "updated_at": _now_iso(),
        }
        self.policy_path.parent.mkdir(
            parents=True, exist_ok=True, mode=0o700
        )
        self.policy_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        try:
            os.chmod(self.policy_path, 0o600)
        except OSError:  # pragma: no cover - filesystem-specific
            pass

    # -- queries ------------------------------------------------

    def is_enabled(self, name: str) -> bool:
        entry = self._state.get(name)
        if entry is None:
            return True
        return bool(entry["enabled"])

    def is_consented(self, name: str) -> bool:
        entry = self._state.get(name)
        if entry is None:
            return False
        return entry["consented_at"] is not None

    def state(self, name: str) -> dict[str, Any]:
        entry = self._state.get(name)
        if entry is None:
            return {
                "enabled": True,
                "consented_at": None,
            }
        return dict(entry)

    # -- mutations ----------------------------------------------

    def enable(self, name: str) -> None:
        self._ensure(name)
        self._state[name]["enabled"] = True  # type: ignore[assignment]
        self._save()

    def disable(self, name: str) -> None:
        self._ensure(name)
        self._state[name]["enabled"] = False  # type: ignore[assignment]
        self._save()

    def grant_consent(self, name: str) -> None:
        self._ensure(name)
        self._state[name]["consented_at"] = _now_iso()
        self._save()

    def revoke_consent(self, name: str) -> None:
        self._ensure(name)
        self._state[name]["consented_at"] = None
        self._save()

    def require_consent(
        self, name: str, requires_consent: bool
    ) -> None:
        """Raise :class:`ConsentRequired` if needed; no-op otherwise."""
        if not requires_consent:
            return
        if not self.is_consented(name):
            raise ConsentRequired(
                f"Skill {name!r} needs consent before it can "
                f"run.  Grant it with: `akande skill consent "
                f"{name}`."
            )

    # -- internals ----------------------------------------------

    def _ensure(self, name: str) -> None:
        if name not in self._state:
            self._state[name] = {
                "enabled": True,
                "consented_at": None,
            }
