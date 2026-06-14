# Copyright (C) 2026 Sebastien Rousseau.
#
# Licensed under the Apache License, Version 2.0 (the "License").
"""Tests for the akande.skills protocol + registry."""


import pytest

from akande.skills.base import (
    Intent,
    Skill,
    SkillContext,
    SkillMeta,
    SkillRegistry,
    SkillResult,
)


class _Echo(Skill):
    """Echos its raw text back, matching everything non-empty."""

    @property
    def meta(self) -> SkillMeta:
        return SkillMeta(
            name="echo", description="echo skill"
        )

    def match(self, text: str) -> Intent | None:
        if not text.strip():
            return None
        return Intent(
            name="echo",
            args={"text": text},
            raw_text=text,
        )

    def handle(
        self, intent: Intent, ctx: SkillContext
    ) -> SkillResult:
        return SkillResult(
            content=str(intent.args.get("text") or "")
        )


class _StrictMatch(Skill):
    """Only matches when the text starts with a keyword."""

    def __init__(self, name: str, keyword: str) -> None:
        self._name = name
        self._keyword = keyword

    @property
    def meta(self) -> SkillMeta:
        return SkillMeta(
            name=self._name, description="strict match"
        )

    def match(self, text: str) -> Intent | None:
        if text.startswith(self._keyword):
            return Intent(
                name=self._name,
                args={},
                raw_text=text,
            )
        return None

    def handle(
        self, intent: Intent, ctx: SkillContext
    ) -> SkillResult:
        return SkillResult(content=self._name)


class TestRegistry:
    def test_register_and_list(self):
        reg = SkillRegistry()
        reg.register(_Echo())
        assert reg.names() == ["echo"]
        assert reg.get("echo") is not None

    def test_register_unnamed_raises(self):
        class _Anon(_Echo):
            @property
            def meta(self) -> SkillMeta:
                return SkillMeta(
                    name="", description="anon"
                )

        with pytest.raises(ValueError):
            SkillRegistry().register(_Anon())

    def test_duplicate_register_raises(self):
        reg = SkillRegistry()
        reg.register(_Echo())
        with pytest.raises(ValueError):
            reg.register(_Echo())

    def test_disable_hides_from_names(self):
        reg = SkillRegistry()
        reg.register(_Echo())
        reg.disable("echo")
        assert reg.names() == []
        assert reg.get("echo") is None
        reg.enable("echo")
        assert "echo" in reg.names()

    def test_route_picks_first_match(self):
        reg = SkillRegistry()
        # Strict match first.
        reg.register(_StrictMatch("hi", "hello"))
        reg.register(_Echo())
        match = reg.route("hello there")
        assert match is not None
        skill, intent = match
        assert skill.meta.name == "hi"

    def test_route_falls_through_to_universal(self):
        reg = SkillRegistry()
        reg.register(_StrictMatch("only_xyz", "xyz"))
        reg.register(_Echo())
        match = reg.route("hi")
        assert match is not None
        skill, _ = match
        assert skill.meta.name == "echo"

    def test_route_returns_none_when_no_match(self):
        reg = SkillRegistry()
        reg.register(_StrictMatch("never", "🦄"))
        assert reg.route("hi") is None
