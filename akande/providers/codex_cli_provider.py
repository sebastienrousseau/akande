# Copyright (C) 2026 Sebastien Rousseau.
#
# Licensed under the Apache License, Version 2.0 (the "License").
"""Provider that piggybacks on the local OpenAI Codex CLI session.

OpenAI's ``codex`` CLI (``@openai/codex``) is an agentic coding
assistant analogous to Claude Code.  When the user already has the
binary installed and signed in, this provider lets Àkàndé issue
prompts through that session — no ``OPENAI_API_KEY`` required in
the environment.
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


class CodexCliProvider(LLMProvider):
    """Wraps the local ``codex`` (OpenAI Codex) CLI as an LLM provider.

    No API key in env required — the CLI uses its own login session.
    """

    _CLI_NAME = "codex"

    @property
    def provider_name(self) -> str:
        return "codex_cli"

    def __init__(self) -> None:
        cli_path = shutil.which(self._CLI_NAME)
        if cli_path is None:
            raise ImportError(
                "The `codex` CLI (OpenAI Codex) is required for "
                "the 'codex_cli' provider.  Install it via "
                "`npm install -g @openai/codex` and run `codex` "
                "once to log in."
            )
        self._cli_path = cli_path
        # `gpt-5-codex` is the current Codex CLI default.  Caller
        # can override via the `model` argument or by setting
        # OPENAI_DEFAULT_MODEL.
        self._default_model = "gpt-5-codex"

    def _run(
        self,
        user_prompt: str,
        system_prompt: str,
        model: str,
    ) -> str:
        from akande.config import API_CALL_TIMEOUT

        # `codex exec` is the non-interactive entrypoint; reads
        # the prompt from stdin when no positional arg is given.
        cmd: list[str] = [self._cli_path, "exec"]
        chosen = model or self._default_model
        if chosen:
            cmd.extend(["--model", chosen])
        # Codex does not expose a `--system` flag yet; fold the
        # system prompt into the user-visible prompt instead.
        combined_input = user_prompt
        if system_prompt:
            combined_input = (
                f"<system>\n{system_prompt}\n</system>\n\n{user_prompt}"
            )

        start = time.time()
        logger.info(
            "codex CLI request",
            extra={
                "event": "LLM:RequestSent",
                "extra_data": {
                    "provider": self.provider_name,
                    "model": chosen,
                },
            },
        )
        try:
            # nosec B603 — argv list, no shell, path resolved by
            # shutil.which on init.
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
                f"codex CLI timed out after {API_CALL_TIMEOUT}s"
            ) from exc
        except (
            subprocess.CalledProcessError
        ) as exc:  # pragma: no cover - upstream failure
            stderr = (exc.stderr or "").strip()[:200]
            raise RuntimeError(
                f"codex CLI exited {exc.returncode}: {stderr}"
            ) from exc

        latency_ms = (time.time() - start) * 1000
        content = result.stdout.strip()
        logger.info(
            "codex CLI response",
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
        """Stream the response as a single chunk.

        Codex's ``exec`` mode returns the full completion on exit;
        proper token streaming would need ``codex stream`` (when
        the CLI exposes it) or its WebSocket transport.
        """
        response = await self.generate_response(
            user_prompt, system_prompt, model, params
        )
        text = response.choices[0].message.content or ""
        if text:
            yield text
