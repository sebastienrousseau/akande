<!-- SPDX-FileCopyrightText: 2026 Sebastien Rousseau <sebastian.rousseau@gmail.com> -->
<!-- SPDX-License-Identifier: Apache-2.0 OR MIT -->

# AGENTS.md

Invariants for AI-assisted contributions to `akande`. Read this before changing anything.

Everything here applies equally to humans and automated agents. It is addressed to agents because agents can make breaking changes across multiple files before anyone notices.

## 1. Core Invariants

1. **Strict SemVer sequencing policy**: Public releases stay on the `0.0.x` line and increment strictly by `0.0.1`. Never manually edit version numbers outside the active release branch `feat/v<next-version>`. `v0.1.0` is forbidden until `v0.0.999` exists.
2. **Single Active Release PR Invariant**: Across all repositories, there MUST be at most ONE active pull request targeting `main`, which MUST be the release iteration branch `feat/v<next-version>`.
3. **Branch Funneling Policy**: Any Dependabot PRs, security fixes, documentation updates, or auxiliary topic branches MUST NEVER be merged directly into `main`. They MUST ALWAYS be merged into the active `feat/v<next-version>` branch, and their standalone PRs targeting `main` closed. All iteration work funnels into the single release PR.
4. **Dual licensing**: The repository is dual-licensed under Apache-2.0 OR MIT. All files must declare an SPDX license header.
5. **Single source of truth**: The version in `pyproject.toml` (`[project] version`) is the single source of truth. It must agree with `akande/__init__.py` and `CITATION.cff`.
6. **Input sanitization & safety**: All audio and text inputs are sanitized, length-clamped, and wrapped in the safety envelope before calling any LLM provider.
7. **SSRF prevention**: Network tools such as `fetch_url` must strictly validate destination hosts and IPs against RFC 1918 subnets, loopbacks, link-local addresses, and cloud metadata services.

## 2. Before You Claim To Be Done (Verification Gates)

Before concluding any task or preparing a commit, run:

```console
uv run --extra dev pytest
uv run --extra dev ruff check .
uv run --extra dev ruff format --check .
uv run --extra dev mypy akande
```

## 3. Things That Look Like Bugs and Are Not

- **PyAudio is optional**: `akande` operates without `pyaudio` for CLI, web server, and text interactions. Install `akande[mic]` for microphone capture.
- **Provider SDKs are modular**: Providers only require their optional extras (`akande[anthropic]`, `akande[google]`, etc.).
