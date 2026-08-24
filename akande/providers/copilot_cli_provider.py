# Copyright (C) 2026 Sebastien Rousseau.
#
# Licensed under the Apache License, Version 2.0 (the "License").
"""Provider that piggybacks on the GitHub Copilot CLI session.

GitHub Copilot ships an agentic CLI (``gh copilot`` / ``copilot``)
that uses the user's GitHub-side Copilot subscription.  When the
binary is installed and authenticated, this provider lets Àkàndé
issue prompts through that session — no GitHub PAT required in
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


class CopilotCliProvider(LLMProvider):
    """Wraps the GitHub Copilot CLI as an LLM provider.

    No PAT in env required — the CLI uses ``gh``'s OAuth session.
    """

    @property
    def provider_name(self) -> str:
        return "copilot_cli"

    def __init__(self) -> None:
        # Prefer the standalone `copilot` binary when present; fall
        # back to ``gh copilot`` for the gh-extension flavour.
        standalone = shutil.which("copilot")
        gh = shutil.which("gh")
        if standalone is not None:
            self._cli_path = standalone
            self._cli_argv: list[str] = [standalone]
        elif gh is not None:
            self._cli_path = gh
            self._cli_argv = [gh, "copilot"]
        else:
            raise ImportError(
                "The GitHub Copilot CLI is required for the "
                "'copilot_cli' provider.  Install the `copilot` "
                "binary or the `gh-copilot` extension "
                "(`gh extension install github/gh-copilot`), then "
                "run `gh auth login` once."
            )
        # Copilot's CLI does not surface a model selector to the
        # user (the backing model is chosen server-side).  We
        # report the marker `auto` so the status bar has something
        # meaningful to show.
        self._default_model = "auto"

    def _run(
        self,
        user_prompt: str,
        system_prompt: str,
        model: str,
    ) -> str:
        from akande.config import API_CALL_TIMEOUT

        # Copilot's chat surface is `copilot chat`.  When that
        # subcommand is missing we fall back to `copilot suggest`
        # which is the older single-shot question form.
        cmd = list(self._cli_argv) + ["chat", "--no-color"]
        combined_input = user_prompt
        if system_prompt:
            combined_input = (
                f"<system>\n{system_prompt}\n</system>\n\n{user_prompt}"
            )

        start = time.time()
        logger.info(
            "copilot CLI request",
            extra={
                "event": "LLM:RequestSent",
                "extra_data": {
                    "provider": self.provider_name,
                    "model": model or self._default_model,
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
                f"copilot CLI timed out after {API_CALL_TIMEOUT}s"
            ) from exc
        except (
            subprocess.CalledProcessError
        ) as exc:  # pragma: no cover - upstream failure
            stderr = (exc.stderr or "").strip()[:200]
            raise RuntimeError(
                f"copilot CLI exited {exc.returncode}: {stderr}"
            ) from exc

        latency_ms = (time.time() - start) * 1000
        content = result.stdout.strip()
        logger.info(
            "copilot CLI response",
            extra={
                "event": "LLM:ResponseReceived",
                "extra_data": {
                    "provider": self.provider_name,
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
        """Yield the response as one chunk (Copilot CLI is sync)."""
        response = await self.generate_response(
            user_prompt, system_prompt, model, params
        )
        text = response.choices[0].message.content or ""
        if text:
            yield text
