# Copyright (C) 2026 Sebastien Rousseau.
#
# Licensed under the Apache License, Version 2.0 (the "License").
"""Provider that piggybacks on Google's Antigravity CLI session.

Google's Antigravity (https://antigravity.google) ships an
agentic CLI alongside its IDE.  When the user has the
``antigravity`` binary installed and signed in, this provider
lets Àkàndé issue prompts through that session — no
``GOOGLE_API_KEY`` required in the environment.

This is a best-effort wrapper; the Antigravity CLI is still
evolving and exact flags may shift between releases.  Future
Àkàndé point releases will track the canonical CLI surface.
"""

from __future__ import annotations

import asyncio
import logging
import shutil
import subprocess  # nosec B404 — vetted local binary
import time
from collections.abc import AsyncIterator
from typing import Any

from .base import LLMProvider
from .response import ProviderResponse

logger = logging.getLogger(__name__)


class AntigravityCliProvider(LLMProvider):
    """Wraps Google's Antigravity CLI as an LLM provider.

    No API key in env required — the CLI uses its own login.
    """

    _CLI_NAME = "antigravity"

    @property
    def provider_name(self) -> str:
        return "antigravity_cli"

    def __init__(self) -> None:
        cli_path = shutil.which(self._CLI_NAME)
        if cli_path is None:
            raise ImportError(
                "The `antigravity` CLI (Google Antigravity) is "
                "required for the 'antigravity_cli' provider.  "
                "Install it from https://antigravity.google and "
                "run `antigravity login` once."
            )
        self._cli_path = cli_path
        # Gemini 2.5 Pro is the public Antigravity default at
        # release.  Caller can override via the `model` argument
        # or by setting OPENAI_DEFAULT_MODEL.
        self._default_model = "gemini-2.5-pro"

    def _run(
        self,
        user_prompt: str,
        system_prompt: str,
        model: str,
    ) -> str:
        from akande.config import API_CALL_TIMEOUT

        # `antigravity prompt --print` is the documented non-
        # interactive entrypoint; it reads the prompt from stdin
        # when no positional arg is supplied.
        cmd: list[str] = [self._cli_path, "prompt", "--print"]
        chosen = model or self._default_model
        if chosen:
            cmd.extend(["--model", chosen])
        combined_input = user_prompt
        if system_prompt:
            combined_input = (
                f"<system>\n{system_prompt}\n</system>\n\n{user_prompt}"
            )

        start = time.time()
        logger.info(
            "antigravity CLI request",
            extra={
                "event": "LLM:RequestSent",
                "extra_data": {
                    "provider": self.provider_name,
                    "model": chosen,
                },
            },
        )
        try:
            # nosec B603 — argv list, no shell.
            result = subprocess.run(  # noqa: S603
                cmd,
                input=combined_input,
                capture_output=True,
                text=True,
                timeout=API_CALL_TIMEOUT,
                check=True,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(
                f"antigravity CLI timed out after {API_CALL_TIMEOUT}s"
            ) from exc
        except (
            subprocess.CalledProcessError
        ) as exc:  # pragma: no cover - upstream failure
            stderr = (exc.stderr or "").strip()[:200]
            raise RuntimeError(
                f"antigravity CLI exited {exc.returncode}: {stderr}"
            ) from exc

        latency_ms = (time.time() - start) * 1000
        content = result.stdout.strip()
        logger.info(
            "antigravity CLI response",
            extra={
                "event": "LLM:ResponseReceived",
                "extra_data": {
                    "provider": self.provider_name,
                    "model": chosen,
                    "latency_ms": round(latency_ms, 2),
                    "chars": len(content),
                },
            },
        )
        return content

    def generate_response_sync(
        self,
        user_prompt: str,
        system_prompt: str,
        model: str,
        params: dict[str, Any] | None = None,
    ) -> ProviderResponse:
        text = self._run(user_prompt, system_prompt, model)
        return ProviderResponse(text)

    async def generate_response(
        self,
        user_prompt: str,
        system_prompt: str,
        model: str,
        params: dict[str, Any] | None = None,
    ) -> ProviderResponse:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            self.generate_response_sync,
            user_prompt,
            system_prompt,
            model,
            params,
        )

    async def generate_stream(  # pragma: no cover - subprocess
        self,
        user_prompt: str,
        system_prompt: str,
        model: str,
        params: dict[str, Any] | None = None,
    ) -> AsyncIterator[str]:
        """Yield the response as one chunk."""
        response = await self.generate_response(
            user_prompt, system_prompt, model, params
        )
        text = response.choices[0].message.content or ""
        if text:
            yield text
