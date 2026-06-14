# Copyright (C) 2026 Sebastien Rousseau.
#
# Licensed under the Apache License, Version 2.0 (the "License").
"""``web_search`` — DuckDuckGo HTML scrape with provider fallbacks.

Why DuckDuckGo's HTML endpoint first?  It is the only mainstream
search engine that returns useful results without an API key and
without JavaScript, which keeps the dependency footprint minimal
and respects ``AKANDE_MODE=online`` without forcing operators to
sign up for Tavily / Brave.  When ``BRAVE_API_KEY`` or
``TAVILY_API_KEY`` is set we use those instead — they give better
relevance and structured snippets.

This tool is a *retrieval* surface, not an HTML renderer.  Each
result is reduced to ``{title, url, snippet}`` so the LLM has a
stable contract regardless of which backend served the answer.
"""

from __future__ import annotations

import json
import logging
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from html import unescape
from typing import Any, Dict, List

from .base import Tool, ToolError, ToolResult

logger = logging.getLogger(__name__)

USER_AGENT = (
    "akande/0.0.6 (+https://github.com/sebastienrousseau/"
    "akande)"
)
DEFAULT_LIMIT = 5
TIMEOUT_S = 8.0


class WebSearchTool(Tool):
    name = "web_search"
    description = (
        "Search the public web for a query and return the top "
        "results.  Backed by Brave Search when BRAVE_API_KEY "
        "is set, Tavily when TAVILY_API_KEY is set, and a "
        "key-less DuckDuckGo HTML scrape otherwise."
    )

    @property
    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "What to search for",
                },
                "limit": {
                    "type": "integer",
                    "description": (
                        "Maximum number of results (default 5, "
                        "max 10)"
                    ),
                    "minimum": 1,
                    "maximum": 10,
                },
            },
            "required": ["query"],
        }

    def run(self, args: Dict[str, Any]) -> ToolResult:
        query = (args.get("query") or "").strip()
        if not query:
            raise ToolError(
                "web_search requires a non-empty 'query'"
            )
        limit = int(args.get("limit") or DEFAULT_LIMIT)
        limit = max(1, min(limit, 10))

        backend, results = self._search(query, limit)
        if not results:
            return ToolResult(
                content=(
                    f"No results found for {query!r} "
                    f"(backend={backend})."
                ),
                metadata={"backend": backend, "count": 0},
            )
        rendered = self._render(query, backend, results)
        return ToolResult(
            content=rendered,
            metadata={
                "backend": backend,
                "count": len(results),
            },
        )

    # -- internals -------------------------------------------------

    def _search(
        self, query: str, limit: int
    ) -> tuple[str, List[Dict[str, str]]]:
        if os.getenv("BRAVE_API_KEY"):
            try:
                return "brave", self._brave(query, limit)
            except Exception as exc:
                logger.warning(
                    "Brave search failed",
                    exc_info=True,
                    extra={
                        "event": "Tool:WebSearchBraveFailed",
                        "extra_data": {
                            "error": type(exc).__name__,
                        },
                    },
                )
        if os.getenv("TAVILY_API_KEY"):
            try:
                return "tavily", self._tavily(query, limit)
            except Exception as exc:
                logger.warning(
                    "Tavily search failed",
                    exc_info=True,
                    extra={
                        "event": "Tool:WebSearchTavilyFailed",
                        "extra_data": {
                            "error": type(exc).__name__,
                        },
                    },
                )
        return "duckduckgo", self._duckduckgo(query, limit)

    def _brave(
        self, query: str, limit: int
    ) -> List[Dict[str, str]]:
        url = (
            "https://api.search.brave.com/res/v1/web/search?"
            + urllib.parse.urlencode(
                {"q": query, "count": limit}
            )
        )
        req = urllib.request.Request(
            url,
            headers={
                "X-Subscription-Token": os.environ[
                    "BRAVE_API_KEY"
                ],
                "Accept": "application/json",
                "User-Agent": USER_AGENT,
            },
        )
        # nosec B310 — endpoints are hard-coded HTTPS URLs to known
        # search providers; the permitted-schemes warning is N/A.
        with urllib.request.urlopen(  # nosec B310
            req, timeout=TIMEOUT_S
        ) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        web = (payload.get("web") or {}).get("results") or []
        return [
            {
                "title": str(r.get("title", "")),
                "url": str(r.get("url", "")),
                "snippet": str(r.get("description", "")),
            }
            for r in web[:limit]
        ]

    def _tavily(
        self, query: str, limit: int
    ) -> List[Dict[str, str]]:
        body = json.dumps(
            {
                "api_key": os.environ["TAVILY_API_KEY"],
                "query": query,
                "max_results": limit,
            }
        ).encode("utf-8")
        req = urllib.request.Request(
            "https://api.tavily.com/search",
            data=body,
            headers={
                "Content-Type": "application/json",
                "User-Agent": USER_AGENT,
            },
        )
        # nosec B310 — endpoints are hard-coded HTTPS URLs to known
        # search providers; the permitted-schemes warning is N/A.
        with urllib.request.urlopen(  # nosec B310
            req, timeout=TIMEOUT_S
        ) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        return [
            {
                "title": str(r.get("title", "")),
                "url": str(r.get("url", "")),
                "snippet": str(r.get("content", "")),
            }
            for r in (payload.get("results") or [])[:limit]
        ]

    def _duckduckgo(
        self, query: str, limit: int
    ) -> List[Dict[str, str]]:
        url = (
            "https://duckduckgo.com/html/?"
            + urllib.parse.urlencode({"q": query})
        )
        req = urllib.request.Request(
            url, headers={"User-Agent": USER_AGENT}
        )
        try:
            # nosec B310 — hard-coded https://duckduckgo.com endpoint.
            with urllib.request.urlopen(  # nosec B310
                req, timeout=TIMEOUT_S
            ) as resp:
                html = resp.read().decode(
                    "utf-8", errors="ignore"
                )
        except urllib.error.URLError as exc:
            raise ToolError(
                f"web_search backend unreachable: {exc.reason}"
            ) from exc

        # DuckDuckGo's HTML endpoint groups each result as a
        # ``<div class="result results_links">`` with anchor +
        # snippet.  This regex is intentionally loose so layout
        # tweaks at the upstream don't break us silently.
        pattern = re.compile(
            r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>'
            r".*?<a[^>]+class=\"result__snippet\"[^>]*>(.*?)</a>",
            re.DOTALL,
        )
        results: List[Dict[str, str]] = []
        for match in pattern.finditer(html):
            url_raw, title, snippet = match.groups()
            results.append(
                {
                    "title": _strip_tags(title),
                    "url": _unwrap_duckduckgo_url(url_raw),
                    "snippet": _strip_tags(snippet),
                }
            )
            if len(results) >= limit:
                break
        return results

    @staticmethod
    def _render(
        query: str,
        backend: str,
        results: List[Dict[str, str]],
    ) -> str:
        lines = [
            f"Top {len(results)} results for {query!r} "
            f"(via {backend}):",
            "",
        ]
        for i, r in enumerate(results, 1):
            lines.append(f"{i}. {r['title']}")
            lines.append(f"   {r['url']}")
            if r["snippet"]:
                lines.append(f"   {r['snippet']}")
        return "\n".join(lines)


def _strip_tags(html: str) -> str:
    """Cheap HTML→text — no bs4 dep, good enough for snippets."""
    return unescape(re.sub(r"<[^>]+>", "", html)).strip()


def _unwrap_duckduckgo_url(raw: str) -> str:
    """DuckDuckGo wraps outbound links in /l/?uddg=<url>; unwrap if so."""
    if "uddg=" not in raw:
        return raw
    try:
        query = urllib.parse.urlparse(raw).query
        params = urllib.parse.parse_qs(query)
        target = params.get("uddg", [raw])[0]
        return urllib.parse.unquote(target)
    except Exception:
        return raw
