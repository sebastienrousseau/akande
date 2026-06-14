# Copyright (C) 2026 Sebastien Rousseau.
#
# Licensed under the Apache License, Version 2.0 (the "License").
"""Skills — the Àkàndé extension surface.

A *skill* answers a user request that's better served by a
specialised handler than a generic LLM call: "what's the weather
in Paris", "show me AAPL", "summarise this article".  Each skill
declares a :class:`SkillMeta` (name, description, whether it
needs consent, whether it works offline), advertises a
:meth:`Skill.match` predicate the router uses to pick it, and
implements :meth:`Skill.handle` to do the work.

A registry of skills is composable: a :class:`SkillRegistry` is
built from the built-ins (:func:`builtin_skills`) plus any plugin
discovered via the ``akande.skills`` Python entry-point group.
The registry consults :mod:`akande.skills.policy` for per-skill
enable/disable and consent state.

Built-in starter set (v0.0.6-dev.8):

- ``briefing`` — fall back to a BLUF-format LLM briefing (the
  current Àkàndé behaviour, now exposed as a named skill).
- ``web_search`` — wraps :class:`akande.tools.WebSearchTool`.
- ``weather`` — Open-Meteo public API, no key required.
- ``finance`` — Yahoo Finance JSON quote endpoint, no key
  required.

The sandboxed ``shell`` skill stays on the v0.0.6-dev.9 list with
the rest of the security-heavy execution surface.
"""

from __future__ import annotations

from .base import (
    Intent,
    Skill,
    SkillContext,
    SkillMeta,
    SkillRegistry,
    SkillResult,
)
from .briefing import BriefingSkill
from .finance import FinanceSkill
from .weather import WeatherSkill
from .web_search import WebSearchSkill

__all__ = [
    "Intent",
    "Skill",
    "SkillContext",
    "SkillMeta",
    "SkillRegistry",
    "SkillResult",
    "BriefingSkill",
    "FinanceSkill",
    "WeatherSkill",
    "WebSearchSkill",
    "builtin_skills",
    "default_registry",
]


def builtin_skills() -> list[Skill]:
    """Return the canonical starter set of skills."""
    # Order matters — :meth:`SkillRegistry.route` consults skills
    # in registration order, so the more specific ones must come
    # first.  ``briefing`` is the universal fallback and lives
    # last in the chain.
    return [
        WeatherSkill(),
        FinanceSkill(),
        WebSearchSkill(),
        BriefingSkill(),
    ]


def default_registry() -> SkillRegistry:
    """Construct a registry pre-populated with the built-ins.

    Plugin discovery via ``akande.skills`` entry-points lives in
    :meth:`SkillRegistry.discover_plugins` and is best-effort —
    a broken plugin is logged and skipped, not propagated.
    """
    reg = SkillRegistry()
    for skill in builtin_skills():
        reg.register(skill)
    reg.discover_plugins()
    return reg
