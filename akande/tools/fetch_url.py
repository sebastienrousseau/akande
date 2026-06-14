# Copyright (C) 2026 Sebastien Rousseau.
#
# Licensed under the Apache License, Version 2.0 (the "License").
"""``fetch_url`` — pull a URL and return readable text.

The tool is intentionally simple: HTTPS-only (downgrades refused),
size-capped, with a small allowlist of MIME types so the LLM never
sees a base64 image blob in its context window.  No HTML parser
dep — a regex tag strip is good enough for the LLM, and avoids
pulling in lxml just for one tool.
"""

from __future__ import annotations

import logging
import re
import urllib.error
import urllib.parse
import urllib.request
from html import unescape
from typing import Any

from .base import Tool, ToolError, ToolResult

logger = logging.getLogger(__name__)

MAX_BYTES = 1_000_000  # 1 MB cap on the body we ingest
TIMEOUT_S = 8.0
ALLOWED_CONTENT_TYPES = (
    "text/html",
    "text/plain",
    "application/json",
    "application/xml",
    "text/markdown",
    "text/csv",
)
USER_AGENT = "akande/0.0.6 (+fetch_url)"


class FetchURLTool(Tool):
    name = "fetch_url"
    description = (
        "Fetch the body of an HTTPS URL (1 MB cap) and return "
        "the text content with HTML tags stripped.  Refuses "
        "non-HTTPS schemes, binary content types, and "
        "responses larger than the cap."
    )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "HTTPS URL to fetch",
                },
                "max_chars": {
                    "type": "integer",
                    "description": (
                        "Truncate body to this many characters "
                        "(default 8000)"
                    ),
                    "minimum": 100,
                    "maximum": 50_000,
                },
            },
            "required": ["url"],
        }

    def run(self, args: dict[str, Any]) -> ToolResult:
        url = (args.get("url") or "").strip()
        max_chars = int(args.get("max_chars") or 8000)
        max_chars = max(100, min(max_chars, 50_000))

        parsed = urllib.parse.urlparse(url)
        if parsed.scheme != "https":
            raise ToolError("fetch_url requires an https:// URL")
        if not parsed.netloc:
            raise ToolError("fetch_url URL is missing a host")

        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": ", ".join(ALLOWED_CONTENT_TYPES),
            },
        )
        try:
            # nosec B310 — scheme is explicitly validated above to be
            # HTTPS, so bandit's permitted-schemes warning does not apply.
            with urllib.request.urlopen(  # nosec B310
                req, timeout=TIMEOUT_S
            ) as resp:
                content_type = resp.headers.get_content_type() or ""
                if content_type not in ALLOWED_CONTENT_TYPES:
                    raise ToolError(
                        "fetch_url refused content-type "
                        f"{content_type!r}"
                    )
                body = resp.read(MAX_BYTES + 1)
        except urllib.error.HTTPError as exc:
            raise ToolError(
                f"fetch_url HTTP {exc.code}: {exc.reason}"
            ) from exc
        except urllib.error.URLError as exc:
            raise ToolError(f"fetch_url failed: {exc.reason}") from exc

        if len(body) > MAX_BYTES:
            raise ToolError(
                f"fetch_url body exceeded {MAX_BYTES} bytes "
                f"before truncation"
            )

        text = body.decode("utf-8", errors="replace")
        if content_type == "text/html":
            text = _html_to_text(text)
        if len(text) > max_chars:
            text = text[:max_chars] + "\n[truncated]"

        return ToolResult(
            content=text,
            metadata={
                "url": url,
                "content_type": content_type,
                "bytes": len(body),
                "chars": len(text),
            },
        )


_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")


def _html_to_text(html: str) -> str:
    """Minimal HTML→text — drop script/style first, then strip tags."""
    html = re.sub(
        r"<script.*?</script>",
        " ",
        html,
        flags=re.DOTALL | re.IGNORECASE,
    )
    html = re.sub(
        r"<style.*?</style>", " ", html, flags=re.DOTALL | re.IGNORECASE
    )
    text = unescape(_TAG.sub(" ", html))
    return _WS.sub(" ", text).strip()
