# Copyright (C) 2026 Sebastien Rousseau.
#
# Licensed under the Apache License, Version 2.0 (the "License").
"""Core types for the Àkàndé skill surface."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SkillMeta:
    """Static descriptor for a skill.

    Attributes carry the kind of operator-relevant information the
    policy file + ``akande skill list`` care about.  Keep this
    small — anything dynamic lives on the :class:`Skill` instance.
    """

    name: str
    description: str
    version: str = "1.0.0"
    requires_consent: bool = False
    supports_offline: bool = False
    citations_expected: bool = False


@dataclass
class Intent:
    """A matched intent, ready for the skill to handle."""

    name: str
    args: dict[str, Any] = field(default_factory=dict)
    raw_text: str = ""


@dataclass
class SkillResult:
    """Outcome of :meth:`Skill.handle`."""

    content: str
    citations: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SkillContext:
    """Runtime context passed through to every skill invocation."""

    user_id: str = "default"
    conversation_id: str | None = None
    correlation_id: str | None = None


class Skill(ABC):
    """Specialised handler the router picks over a generic LLM call.

    Implementations declare what they can do via :attr:`meta`,
    decide whether the user's text is theirs to handle in
    :meth:`match`, and produce a :class:`SkillResult` in
    :meth:`handle`.  Streaming responses can be reduced to a
    single :class:`SkillResult` and re-chunked by the caller; we
    don't push complexity into the ABC until a built-in actually
    needs it.
    """

    @property
    @abstractmethod
    def meta(self) -> SkillMeta: ...

    @abstractmethod
    def match(self, text: str) -> Intent | None:
        """Return an Intent if this skill claims the request, else None."""
        ...

    @abstractmethod
    def handle(
        self, intent: Intent, ctx: SkillContext
    ) -> SkillResult: ...

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return f"<Skill {self.meta.name}>"


class SkillRegistry:
    """Ordered registry with policy hooks + entry-point discovery."""

    ENTRY_POINT_GROUP = "akande.skills"

    def __init__(self) -> None:
        self._skills: list[Skill] = []
        self._disabled: set[str] = set()

    def register(self, skill: Skill) -> None:
        if not skill.meta.name:
            raise ValueError("skill must declare a non-empty name")
        if any(s.meta.name == skill.meta.name for s in self._skills):
            raise ValueError(
                f"skill {skill.meta.name!r} already registered"
            )
        self._skills.append(skill)

    def names(self) -> list[str]:
        return [
            s.meta.name
            for s in self._skills
            if s.meta.name not in self._disabled
        ]

    def all(self) -> list[Skill]:
        return [
            s for s in self._skills if s.meta.name not in self._disabled
        ]

    def get(self, name: str) -> Skill | None:
        if name in self._disabled:
            return None
        for s in self._skills:
            if s.meta.name == name:
                return s
        return None

    def disable(self, name: str) -> None:
        self._disabled.add(name)

    def enable(self, name: str) -> None:
        self._disabled.discard(name)

    def route(self, text: str) -> tuple[Skill, Intent] | None:
        """Find the first skill that claims the text.

        Returns ``(skill, intent)`` or ``None`` when nothing
        matches.  The caller is responsible for consent
        enforcement via :mod:`akande.skills.policy`.
        """
        for skill in self.all():
            intent = skill.match(text)
            if intent is not None:
                return skill, intent
        return None

    def discover_plugins(self) -> None:
        """Register skills advertised via the ``akande.skills``
        entry-point group.

        Errors during plugin load are logged and swallowed —
        a broken plugin must never prevent Àkàndé from starting.
        """
        try:
            from importlib.metadata import entry_points
        except ImportError:  # pragma: no cover - py<3.10 fallback
            return
        eps = entry_points()
        if hasattr(eps, "select"):  # py3.10+
            candidates = list(eps.select(group=self.ENTRY_POINT_GROUP))
        else:  # pragma: no cover
            # Pre-3.10 EntryPoints exposes ``get`` returning a list.
            getter = getattr(eps, "get", None)
            candidates = (
                list(getter(self.ENTRY_POINT_GROUP, []))
                if getter is not None
                else []
            )
        for ep in candidates:
            try:
                obj = ep.load()
                instance = obj() if callable(obj) else obj
                if isinstance(
                    instance, Skill
                ):  # pragma: no cover - real plugin registration
                    self.register(instance)
                    logger.info(
                        "Plugin skill registered",
                        extra={
                            "event": "Skill:PluginRegistered",
                            "extra_data": {
                                "name": instance.meta.name,
                                "entry_point": ep.value,
                            },
                        },
                    )
                else:
                    logger.warning(
                        "Plugin %r did not yield a Skill",
                        ep.value,
                    )
            except Exception as exc:  # pragma: no cover
                logger.warning(
                    "Plugin %r failed to load: %s",
                    ep.value,
                    exc,
                    extra={
                        "event": "Skill:PluginFailed",
                    },
                )
