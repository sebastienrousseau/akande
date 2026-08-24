# Copyright (C) 2026 Sebastien Rousseau.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
"""Provider that piggybacks on the local Claude Code CLI session.

When the user already has the ``claude`` CLI installed and logged in,
this provider lets Àkàndé issue prompts through that session instead
of requiring an ``ANTHROPIC_API_KEY`` in the environment.  Auth, rate
limits, and quota are handled entirely by the CLI; we just shell out.

This is intentionally the *only* provider that does not connect to a
network endpoint directly — it inherits whatever the CLI is configured
to talk to (cloud Anthropic, an enterprise proxy, etc.).
"""

from __future__ import annotations

import asyncio
import logging
import shutil
import subprocess  # nosec B404 — we shell out to a vetted local binary
import time
from collections.abc import AsyncIterator
from typing import Any

from .base import LLMProvider
from .response import ProviderResponse

logger = logging.getLogger(__name__)


class ClaudeCliProvider(LLMProvider):
    """Wraps the local ``claude`` (Claude Code) CLI as an LLM provider.

    No API key in env required — the CLI uses its own login session.
    """

    _CLI_NAME = "claude"

    @property
    def provider_name(self) -> str:
        return "claude_cli"

    def __init__(self) -> None:
        cli_path = shutil.which(self._CLI_NAME)
        if cli_path is None:
            raise ImportError(
                "The `claude` CLI (Claude Code) is required for the "
                "'claude_cli' provider.  Install it from "
                "https://docs.claude.com/claude-code or via "
                "`npm install -g @anthropic-ai/claude-code`, then "
                "run `claude` once to log in."
            )
        self._cli_path = cli_path
        # Sonnet is Claude Code's own default; matches the README
        # provider table.  Caller can override via the `model`
        # argument or by setting OPENAI_DEFAULT_MODEL.
        self._default_model = "sonnet"

    def _run(
        self,
        user_prompt: str,
        system_prompt: str,
        model: str,
    ) -> str:
        from akande.config import API_CALL_TIMEOUT

        cmd: list[str] = [self._cli_path, "-p"]
        if system_prompt:
            cmd.extend(["--append-system-prompt", system_prompt])
        # Pass --model when the caller asked for something specific.
        # Skip well-known openai-shaped defaults so a stray
        # `OPENAI_DEFAULT_MODEL=gpt-4o-mini` doesn't crash the CLI.
        chosen = model or self._default_model
        if chosen and not chosen.startswith("gpt-"):
            cmd.extend(["--model", chosen])

        start = time.time()
        logger.info(
            "claude CLI request",
            extra={
                "event": "LLM:RequestSent",
                "extra_data": {
                    "provider": self.provider_name,
                    "model": chosen,
                },
            },
        )
        try:
            # nosec B603 — argv list, no shell, executable path is the
            # one resolved by shutil.which on init.
            result = subprocess.run(  # noqa: S603
                cmd,
                input=user_prompt,
                capture_output=True,
                text=True,
                timeout=API_CALL_TIMEOUT,
                check=True,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(
                f"claude CLI timed out after {API_CALL_TIMEOUT}s"
            ) from exc
        except (
            subprocess.CalledProcessError
        ) as exc:  # pragma: no cover - upstream failure
            stderr = (exc.stderr or "").strip()[:200]
            raise RuntimeError(
                f"claude CLI exited {exc.returncode}: {stderr}"
            ) from exc

        latency_ms = (time.time() - start) * 1000
        content = result.stdout.strip()
        logger.info(
            "claude CLI response",
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

    async def generate_stream(
        self,
        user_prompt: str,
        system_prompt: str,
        model: str,
        params: dict[str, Any] | None = None,
    ) -> AsyncIterator[str]:
        """Stream text deltas from the local Claude Code CLI.

        Spawns ``claude -p --output-format stream-json
        --include-partial-messages --verbose`` and parses each JSONL
        line as it arrives, yielding the text of every
        ``content_block_delta`` event.  Other event types
        (system/init, rate_limit_event, message_start/stop, etc.)
        are skipped.
        """
        async for delta in self._stream_argv(
            user_prompt, system_prompt, model
        ):
            yield delta

    async def generate_stream_messages(
        self,
        messages: list[dict[str, str]],
        model: str,
        params: dict[str, Any] | None = None,
    ) -> AsyncIterator[str]:
        """Multi-turn streaming entry-point used by the server.

        Collapses the OpenAI-shaped message list into the
        single-turn shape the CLI accepts (system + last user
        turn), then delegates to :meth:`generate_stream`.  Earlier
        assistant turns are folded into the system prompt as a
        transcript so the CLI sees the conversation history.
        """
        system_prompt = ""
        history: list[dict[str, str]] = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system" and not system_prompt:
                system_prompt = content
                continue
            history.append({"role": role, "content": content})

        if history and history[-1].get("role") == "user":
            current_user = history[-1]["content"]
            prior = history[:-1]
        else:
            current_user = ""
            prior = history

        if prior:
            transcript = "\n".join(
                f"{m['role']}: {m['content']}" for m in prior
            )
            system_with_history = (
                f"{system_prompt}\n\n"
                "<previous_conversation>\n"
                f"{transcript}\n"
                "</previous_conversation>"
            )
        else:
            system_with_history = system_prompt

        async for delta in self._stream_argv(
            current_user, system_with_history, model
        ):
            yield delta

    async def _stream_argv(  # noqa: C901 — straightforward state machine
        self,
        user_prompt: str,
        system_prompt: str,
        model: str,
    ) -> AsyncIterator[str]:
        import json as _json

        from akande.config import API_CALL_TIMEOUT

        cmd: list[str] = [
            self._cli_path,
            "-p",
            "--output-format",
            "stream-json",
            "--include-partial-messages",
            "--verbose",
        ]
        if system_prompt:
            cmd.extend(["--append-system-prompt", system_prompt])
        chosen = model or self._default_model
        if chosen and not chosen.startswith("gpt-"):
            cmd.extend(["--model", chosen])

        start = time.time()
        logger.info(
            "claude CLI stream open",
            extra={
                "event": "LLM:StreamRequestSent",
                "extra_data": {
                    "provider": self.provider_name,
                    "model": chosen,
                },
            },
        )
        # nosec B603 — argv list, no shell, path resolved by
        # shutil.which on init.
        proc = await asyncio.create_subprocess_exec(  # noqa: S603
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        assert proc.stdin is not None and proc.stdout is not None
        stdin = proc.stdin
        stdout = proc.stdout

        async def _feed_stdin() -> None:
            try:
                stdin.write(user_prompt.encode("utf-8"))
                await stdin.drain()
            finally:
                stdin.close()

        feeder = asyncio.create_task(_feed_stdin())
        chunk_count = 0
        try:
            while True:
                try:
                    line = await asyncio.wait_for(
                        stdout.readline(),
                        timeout=API_CALL_TIMEOUT,
                    )
                except asyncio.TimeoutError as exc:  # pragma: no cover
                    proc.kill()
                    raise RuntimeError(
                        f"claude CLI stream timed out after "
                        f"{API_CALL_TIMEOUT}s"
                    ) from exc
                if not line:
                    break
                try:
                    payload = _json.loads(line.decode("utf-8"))
                except (
                    ValueError,
                    UnicodeDecodeError,
                ):  # pragma: no cover
                    continue
                if payload.get("type") != "stream_event":
                    continue
                event = payload.get("event") or {}
                if event.get("type") != "content_block_delta":
                    continue
                delta = (event.get("delta") or {}).get("text", "")
                if delta:
                    chunk_count += 1
                    yield delta
        finally:
            await feeder
            await proc.wait()
            latency_ms = (time.time() - start) * 1000
            logger.info(
                "claude CLI stream completed",
                extra={
                    "event": "LLM:StreamCompleted",
                    "extra_data": {
                        "provider": self.provider_name,
                        "model": chosen,
                        "chunks": chunk_count,
                        "latency_ms": round(latency_ms, 2),
                        "exit_code": proc.returncode,
                    },
                },
            )
