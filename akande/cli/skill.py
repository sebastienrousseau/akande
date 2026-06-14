# Copyright (C) 2026 Sebastien Rousseau.
#
# Licensed under the Apache License, Version 2.0 (the "License").
"""``akande skill {list,enable,disable,consent,revoke}``.

Manage the skill registry's enable / consent state from the CLI.
The state file lives at ``$AKANDE_HOME/skills/policy.json`` so a
human can also edit it directly when scripted.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any


def skill_command(ns: argparse.Namespace) -> int:
    sub = getattr(ns, "skill_command", None)
    if sub == "list":
        return _list(ns)
    if sub == "enable":
        return _enable(ns)
    if sub == "disable":
        return _disable(ns)
    if sub == "consent":
        return _consent(ns)
    if sub == "revoke":
        return _revoke(ns)
    print(
        "usage: akande skill {list,enable,disable,consent,revoke} …",
        file=sys.stderr,
    )
    return 2


def _registry_and_policy():
    from akande.skills import default_registry
    from akande.skills.policy import SkillPolicy

    return default_registry(), SkillPolicy()


def _list(ns: argparse.Namespace) -> int:
    registry, policy = _registry_and_policy()
    rows: list[dict[str, Any]] = []
    for skill in registry.all():
        meta = skill.meta
        rows.append(
            {
                "name": meta.name,
                "description": meta.description,
                "version": meta.version,
                "requires_consent": meta.requires_consent,
                "supports_offline": meta.supports_offline,
                "enabled": policy.is_enabled(meta.name),
                "consented": policy.is_consented(meta.name),
            }
        )
    print(json.dumps(rows, sort_keys=True, indent=2))
    return 0


def _enable(ns: argparse.Namespace) -> int:
    _require_known(ns.name)
    _, policy = _registry_and_policy()
    policy.enable(ns.name)
    print(f"✓ enabled skill {ns.name!r}")
    return 0


def _disable(ns: argparse.Namespace) -> int:
    _require_known(ns.name)
    _, policy = _registry_and_policy()
    policy.disable(ns.name)
    print(f"✓ disabled skill {ns.name!r}")
    return 0


def _consent(ns: argparse.Namespace) -> int:
    _require_known(ns.name)
    _, policy = _registry_and_policy()
    policy.grant_consent(ns.name)
    print(f"✓ consent granted for skill {ns.name!r}")
    return 0


def _revoke(ns: argparse.Namespace) -> int:
    _require_known(ns.name)
    _, policy = _registry_and_policy()
    policy.revoke_consent(ns.name)
    print(f"✓ consent revoked for skill {ns.name!r}")
    return 0


def _require_known(name: str) -> None:
    """Refuse mutations on unknown skill names — typos waste data."""
    from akande.skills import default_registry

    registry = default_registry()
    if registry.get(name) is None:
        print(
            f"unknown skill: {name!r}.  Run `akande skill "
            f"list` to see the registered set.",
            file=sys.stderr,
        )
        sys.exit(2)
