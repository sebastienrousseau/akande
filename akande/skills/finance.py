# Copyright (C) 2026 Sebastien Rousseau.
#
# Licensed under the Apache License, Version 2.0 (the "License").
"""Finance skill — Yahoo Finance JSON quote endpoint.

We use the public ``query1.finance.yahoo.com`` quote endpoint
because it returns a small JSON payload, needs no API key, and
covers most equities + indices that operators want a quick number
on.  When the endpoint or any dependent network call fails the
skill returns a graceful textual error rather than raising.

This is a *retrieval* surface, not investment advice — the
rendered output makes that explicit so the user is never surprised.
"""

from __future__ import annotations

import json
import logging
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Optional

from .base import (
    Intent,
    Skill,
    SkillContext,
    SkillMeta,
    SkillResult,
)

logger = logging.getLogger(__name__)

QUOTE_URL = "https://query1.finance.yahoo.com/v7/finance/quote"
USER_AGENT = "akande/0.0.6 (+finance-skill)"
TIMEOUT_S = 6.0
DISCLAIMER = (
    "Not investment advice; prices are delayed up to 15 minutes."
)

_TICKERS = re.compile(
    r"\b(?:price\s+of|quote\s+for|how\s+much\s+is)\s+"
    r"(?P<symbol>[A-Z][A-Z\-\.]{0,9}(?:\s+stock)?)\b",
    re.IGNORECASE,
)
_DOLLAR_SYMBOL = re.compile(
    r"\$(?P<symbol>[A-Z]{1,10})\b"
)


class FinanceSkill(Skill):
    @property
    def meta(self) -> SkillMeta:
        return SkillMeta(
            name="finance",
            description=(
                "Look up the latest delayed market quote for "
                "a ticker (Yahoo Finance JSON; not investment "
                "advice)."
            ),
            requires_consent=False,
            supports_offline=False,
            citations_expected=True,
        )

    def match(self, text: str) -> Optional[Intent]:
        m = _DOLLAR_SYMBOL.search(text)
        if m:
            return Intent(
                name="finance",
                args={
                    "symbol": m.group("symbol").upper()
                },
                raw_text=text,
            )
        m = _TICKERS.search(text)
        if not m:
            return None
        symbol = m.group("symbol").upper().replace(
            " STOCK", ""
        ).strip()
        if not symbol:
            return None
        return Intent(
            name="finance",
            args={"symbol": symbol},
            raw_text=text,
        )

    def handle(
        self, intent: Intent, ctx: SkillContext
    ) -> SkillResult:
        symbol = str(
            intent.args.get("symbol") or ""
        ).strip().upper()
        if not symbol:
            return SkillResult(
                content=(
                    "Finance skill needs a ticker symbol, e.g. "
                    "'price of AAPL'."
                ),
                metadata={"error": "missing_symbol"},
            )
        try:
            quote = self._quote(symbol)
        except _FetchError as exc:
            return SkillResult(
                content=(
                    f"Could not fetch a quote for {symbol}: "
                    f"{exc}"
                ),
                metadata={
                    "error": "fetch_failed",
                    "symbol": symbol,
                },
            )
        if quote is None:
            return SkillResult(
                content=(
                    f"No quote returned for {symbol} — the "
                    f"symbol may be wrong or delisted."
                ),
                metadata={
                    "error": "no_quote",
                    "symbol": symbol,
                },
            )
        return SkillResult(
            content=self._render(quote),
            citations=[
                "https://finance.yahoo.com/quote/"
                + urllib.parse.quote(symbol)
            ],
            metadata={"symbol": symbol, "raw": quote},
        )

    # -- internals --------------------------------------------------

    def _quote(self, symbol: str) -> Optional[dict]:
        url = (
            QUOTE_URL
            + "?"
            + urllib.parse.urlencode({"symbols": symbol})
        )
        req = urllib.request.Request(
            url, headers={"User-Agent": USER_AGENT}
        )
        try:
            # nosec B310 — hard-coded https://query1.finance.yahoo.com.
            with urllib.request.urlopen(  # nosec B310
                req, timeout=TIMEOUT_S
            ) as resp:
                payload = json.loads(
                    resp.read().decode("utf-8")
                )
        except urllib.error.HTTPError as exc:
            raise _FetchError(f"HTTP {exc.code}") from exc
        except urllib.error.URLError as exc:
            raise _FetchError(
                f"network error: {exc.reason}"
            ) from exc
        except json.JSONDecodeError as exc:
            raise _FetchError(
                "malformed JSON from upstream"
            ) from exc
        results = (
            (payload.get("quoteResponse") or {})
            .get("result")
            or []
        )
        if not results:
            return None
        return results[0]

    @staticmethod
    def _render(q: dict) -> str:
        symbol = q.get("symbol", "?")
        price = q.get("regularMarketPrice")
        change = q.get("regularMarketChange")
        change_pct = q.get("regularMarketChangePercent")
        currency = q.get("currency", "")
        name = q.get(
            "shortName", q.get("longName", symbol)
        )
        bits = [f"{symbol} ({name})"]
        if price is not None:
            bits.append(f"  price: {price} {currency}")
        if change is not None and change_pct is not None:
            arrow = "▲" if change >= 0 else "▼"
            bits.append(
                f"  change: {arrow} "
                f"{change:+.2f} ({change_pct:+.2f}%)"
            )
        bits.append(f"  ({DISCLAIMER})")
        return "\n".join(bits)


class _FetchError(RuntimeError):
    pass
