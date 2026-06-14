# Copyright (C) 2026 Sebastien Rousseau.
#
# Licensed under the Apache License, Version 2.0 (the "License").
"""Briefing skill — the universal fallback.

Always matches.  Delegates to the configured LLM provider so the
core Àkàndé behaviour (a BLUF executive briefing) is reachable
through the skill router exactly as it was through the SSE
endpoint.  Lives last in the registration order so the more
specific skills get first refusal.
"""

from __future__ import annotations

import logging

from akande.config import OPENAI_DEFAULT_MODEL
from akande.providers import get_provider
from akande.services import SYSTEM_PROMPT

from .base import Intent, Skill, SkillContext, SkillMeta, SkillResult

logger = logging.getLogger(__name__)


class BriefingSkill(Skill):
    @property
    def meta(self) -> SkillMeta:
        return SkillMeta(
            name="briefing",
            description=(
                "Generate a BLUF-format executive briefing "
                "for any question."
            ),
            version="1.0.0",
            requires_consent=False,
            supports_offline=True,
            citations_expected=False,
        )

    def match(self, text: str) -> Intent | None:
        if not text.strip():
            return None
        return Intent(
            name="briefing", args={"text": text}, raw_text=text
        )

    def handle(
        self, intent: Intent, ctx: SkillContext
    ) -> SkillResult:
        question = str(intent.args.get("text") or "")
        provider = get_provider()
        response = provider.generate_response_sync(
            question,
            SYSTEM_PROMPT,
            OPENAI_DEFAULT_MODEL or "gpt-4o-mini",
            None,
        )
        try:
            content = str(
                response.choices[0].message.content or ""
            )
        except (AttributeError, IndexError, TypeError):
            content = ""
        return SkillResult(
            content=content,
            metadata={
                "provider": getattr(
                    provider, "provider_name", "unknown"
                ),
                "model": (
                    OPENAI_DEFAULT_MODEL or "gpt-4o-mini"
                ),
            },
        )
