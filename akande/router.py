# Copyright (C) 2026 Sebastien Rousseau.
#
# Licensed under the Apache License, Version 2.0 (the "License").
"""Provider router — picks an LLM provider based on policy.

Default policy is ``passthrough``: whatever ``LLM_PROVIDER`` says.
``cost_optimised`` selects the cheapest provider/model meeting a
minimum quality tier from :mod:`akande.pricing`.  More routers can
be added without touching call sites because the entry-point
returns a single ``(provider_name, model)`` tuple.
"""

from __future__ import annotations

import logging
import os
from typing import Tuple

from akande.mode import active_mode
from akande.pricing import cheapest_meeting

logger = logging.getLogger(__name__)


def route() -> Tuple[str, str]:
    """Return ``(provider_name, model)`` per the active router."""
    policy = (
        os.getenv("AKANDE_ROUTER", "passthrough")
        .strip()
        .lower()
    )
    if policy == "cost_optimised":
        return _cost_optimised()
    return _passthrough()


def _passthrough() -> Tuple[str, str]:
    from akande.config import (
        LLM_PROVIDER,
        OPENAI_DEFAULT_MODEL,
    )

    provider = (LLM_PROVIDER or "openai").strip().lower()
    # Empty model means "let the provider pick its default".
    return provider, OPENAI_DEFAULT_MODEL or ""


def _cost_optimised() -> Tuple[str, str]:
    minimum = os.getenv(
        "AKANDE_ROUTER_MIN_TIER", "medium"
    )
    mode = active_mode()
    pick = cheapest_meeting(
        minimum, local_only=not mode.allow_remote_providers
    )
    if pick is None:
        logger.warning(
            "Cost-optimised router found no qualifier "
            "for tier %r — falling back to passthrough",
            minimum,
            extra={
                "event": "Router:NoQualifier",
                "extra_data": {"min_tier": minimum},
            },
        )
        return _passthrough()
    row, est_cost_usd = pick
    logger.info(
        "Router selected cheapest qualifier",
        extra={
            "event": "Router:Selected",
            "extra_data": {
                "provider": row.provider,
                "model": row.model,
                "est_cost_usd": round(est_cost_usd, 6),
                "tier": row.quality_tier,
            },
        },
    )
    return row.provider, row.model
