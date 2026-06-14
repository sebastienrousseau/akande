# Copyright (C) 2026 Sebastien Rousseau.
#
# Licensed under the Apache License, Version 2.0 (the "License").
"""Import every public Àkàndé module and exit non-zero on failure.

Used by ``scripts/regression.sh`` Phase 3 to catch packaging
mistakes that only surface when the package is freshly installed
into an empty environment.  Pure import sanity — no provider
calls, no network, no model loads.

Run directly so a single subprocess gives one pass/fail signal::

    python -m tests.smoke_imports

The matching pytest-driven version lives in
``tests/test_smoke_imports.py`` and runs as part of the normal
suite.
"""

from __future__ import annotations

import importlib
import sys
import traceback

# Every public submodule we expect a fresh install to be able to
# import.  Optional-dep paths (``akande.tts.kokoro_backend``,
# ``akande.stt.faster_whisper_backend``, ``akande.s2s.openai_realtime``,
# ``akande.mcp.server``, ``akande.mcp.client``) sit in a second list
# whose failures are reported but don't fail the smoke — operators
# who skip ``pip install akande[mcp]`` shouldn't see a red bar.
REQUIRED_MODULES: list[str] = [
    "akande",
    "akande.akande",
    "akande.audit",
    "akande.budgets",
    "akande.cache",
    "akande.cli",
    "akande.cli.audit",
    "akande.cli.data",
    "akande.cli.install_local",
    "akande.cli.mcp",
    "akande.cli.skill",
    "akande.config",
    "akande.conversation",
    "akande.db",
    "akande.disclosure",
    "akande.exceptions",
    "akande.logger",
    "akande.memory",
    "akande.mode",
    "akande.pipeline",
    "akande.pricing",
    "akande.profiles",
    "akande.providers",
    "akande.providers.anthropic_provider",
    "akande.providers.azure_openai_provider",
    "akande.providers.base",
    "akande.providers.cohere_provider",
    "akande.providers.google_provider",
    "akande.providers.groq_provider",
    "akande.providers.huggingface_provider",
    "akande.providers.lmstudio_provider",
    "akande.providers.mistral_provider",
    "akande.providers.ollama_provider",
    "akande.providers.openai_provider",
    "akande.providers.registry",
    "akande.providers.response",
    "akande.router",
    "akande.s2s",
    "akande.s2s.base",
    "akande.s2s.gemini_live",
    "akande.safety",
    "akande.server",
    "akande.server.rate_limit",
    "akande.server.server",
    "akande.services",
    "akande.skills",
    "akande.skills.base",
    "akande.skills.briefing",
    "akande.skills.finance",
    "akande.skills.policy",
    "akande.skills.weather",
    "akande.skills.web_search",
    "akande.stt",
    "akande.stt.base",
    "akande.stt.sr_backend",
    "akande.telemetry",
    "akande.tools",
    "akande.tools.base",
    "akande.tools.calling",
    "akande.tools.fetch_url",
    "akande.tools.web_search",
    "akande.tts",
    "akande.tts.base",
    "akande.tts.gtts_backend",
    "akande.tui",
    "akande.utils",
    "akande.watermark",
]

OPTIONAL_MODULES: list[str] = [
    # Heavy optional deps — fail-open if extras aren't installed.
    "akande.tts.kokoro_backend",
    "akande.stt.faster_whisper_backend",
    "akande.s2s.openai_realtime",
    "akande.mcp",
    "akande.mcp.server",
    "akande.mcp.client",
]


def _try_import(name: str) -> tuple[bool, str]:
    try:
        importlib.import_module(name)
        return True, ""
    except Exception:
        return False, traceback.format_exc()


def main() -> int:
    fail_count = 0
    optional_skips = 0

    for module in REQUIRED_MODULES:
        ok, tb = _try_import(module)
        if ok:
            print(f"OK   {module}")
        else:
            fail_count += 1
            print(f"FAIL {module}\n{tb}", file=sys.stderr)

    for module in OPTIONAL_MODULES:
        ok, tb = _try_import(module)
        if ok:
            print(f"OK   {module} (optional)")
        else:
            optional_skips += 1
            print(f"SKIP {module} (optional dep missing)")

    total = len(REQUIRED_MODULES) + len(OPTIONAL_MODULES)
    print(
        f"\nSummary: {total - fail_count - optional_skips} "
        f"required ok, {fail_count} required failed, "
        f"{optional_skips} optional skipped."
    )
    return 1 if fail_count else 0


if __name__ == "__main__":
    sys.exit(main())
