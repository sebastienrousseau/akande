# Copyright (C) 2026 Sebastien Rousseau.
#
# Licensed under the Apache License, Version 2.0 (the "License").
"""Web-search skill — thin wrapper over :mod:`akande.tools.web_search`.

Triggers on intents that look like research requests so the router
can pick the explicit retrieval path over the LLM-only briefing.
"""

from __future__ import annotations

import re
from typing import Optional

from akande.tools.web_search import WebSearchTool

from .base import (
    Intent,
    Skill,
    SkillContext,
    SkillMeta,
    SkillResult,
)

_TRIGGERS = re.compile(
    r"^(?:search(?:\s+(?:for|the\s+web\s+for))?|look\s+up|"
    r"google|find\s+(?:me\s+)?(?:results\s+for|articles\s+about)|"
    r"web\s+search(?:\s+for)?)\s+(?P<q>.+?)\s*$",
    re.IGNORECASE,
)


class WebSearchSkill(Skill):
    def __init__(self) -> None:
        self._tool = WebSearchTool()

    @property
    def meta(self) -> SkillMeta:
        return SkillMeta(
            name="web_search",
            description=(
                "Search the public web for a query "
                "(DuckDuckGo by default; Brave / Tavily when "
                "keys present)."
            ),
            requires_consent=False,
            supports_offline=False,
            citations_expected=True,
        )

    def match(self, text: str) -> Optional[Intent]:
        m = _TRIGGERS.match(text.strip())
        if not m:
            return None
        return Intent(
            name="web_search",
            args={"query": m.group("q").strip()},
            raw_text=text,
        )

    def handle(
        self, intent: Intent, ctx: SkillContext
    ) -> SkillResult:
        query = str(intent.args.get("query") or "").strip()
        result = self._tool.run({"query": query})
        citations: list[str] = []
        # Snapshot URLs by walking the rendered content — the
        # WebSearchTool already enforces the {title, url, snippet}
        # shape so this is a stable parse.
        for line in result.content.splitlines():
            stripped = line.strip()
            if stripped.startswith("https://") or stripped.startswith(
                "http://"
            ):
                citations.append(stripped)
        return SkillResult(
            content=result.content,
            citations=citations,
            metadata=result.metadata,
        )
