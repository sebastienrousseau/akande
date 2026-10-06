<!-- SPDX-License-Identifier: Apache-2.0 OR MIT -->
<!--
README template. Global rules: see ~/Code/AGENTS.md and ~/Code/REPO-STANDARD.md.
Releases adhere strictly to https://github.com/sebastienrousseau/passmcp/releases/tag/v0.0.5
-->

<p align="center">
  <img src="https://cloudcdn.pro/clients/akande/v1/logos/akande.svg" alt="Àkàndé logo" width="128" />
</p>

<h1 align="center">Àkàndé</h1>

<p align="center">
  A self-hosted, provider-agnostic voice assistant that delivers structured executive briefings via voice or text from 11 LLM providers.
</p>

<p align="center">
  <a href="https://github.com/sebastienrousseau/akande/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/sebastienrousseau/akande/ci.yml?branch=main&style=for-the-badge&logo=github&label=Build" alt="Build" /></a>
  <a href="https://pypi.org/project/akande/"><img src="https://img.shields.io/pypi/v/akande?style=for-the-badge&color=fc8d62&logo=pypi" alt="Registry" /></a>
  <a href="docs/README.md"><img src="https://img.shields.io/badge/docs-reference-blue.svg?style=for-the-badge&labelColor=555555&logo=read-the-docs" alt="Docs" /></a>
  <a href="https://scorecard.dev/viewer/?uri=github.com/sebastienrousseau/akande"><img src="https://img.shields.io/badge/OpenSSF%20Scorecard-Monitored-blue?style=for-the-badge&logo=openssf" alt="OpenSSF Scorecard" /></a>
  <a href="LICENSE-APACHE"><img src="https://img.shields.io/badge/license-Apache--2.0%20OR%20MIT-blue.svg?style=for-the-badge" alt="License: Apache-2.0 OR MIT" /></a>
  <a href="docs/POLICIES.md"><img src="https://img.shields.io/badge/python->=3.10-93450a.svg?style=for-the-badge&logo=python" alt="Python >= 3.10" /></a>
</p>

---

## Contents

**Getting started**

- [Install](#install) : PyPI, source, system dependencies
- [Requirements](#requirements) : toolchain floor, platforms
- [Quick Start](#quick-start) : voice briefing in ten lines

**The Àkàndé ecosystem**

- [The Àkàndé ecosystem](#the-àkàndé-ecosystem) : core CLI, web server, MCP, and TUI modules

**Library reference**

- [Capabilities at a glance](#capabilities-at-a-glance) : the current surface by theme
- [Ecosystem comparison](#ecosystem-comparison) : short matrix; full table at [`docs/COMPARISON.md`](docs/COMPARISON.md)
- [Benchmarks](#benchmarks) : headline numbers; full table at [`docs/BENCHMARKS.md`](docs/BENCHMARKS.md)
- [Features](#features) : module-level capability list
- [Configuration](#configuration) : core options
- [Examples](#examples) : runnable example index

**Operational**

- [When not to use Àkàndé](#when-not-to-use-àkàndé) : limitations
- [Development](#development) : make targets, fuzzing, CI
- [Security](#security) : guarantees and compliance
- [Documentation](#documentation) : all reference docs
- [Stability guarantees](#stability-guarantees) : SemVer axis, output stability, minimum toolchain discipline
- [License](#license)

---

## Install

### As a Python library

```toml
[dependencies]
akande = "^0.0.7"
```

```bash
# Core install : provider SDKs and mic capture are optional extras
pip install akande

# Full kit : every provider + microphone + MCP
pip install "akande[all,mic,mcp]"
```

### From source

```bash
git clone https://github.com/sebastienrousseau/akande
cd akande
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

---

## Requirements

| Requirement | Supported Version | Details |
| :--- | :--- | :--- |
| **Python** | `>= 3.10` (tested on 3.10, 3.11, 3.12, 3.13, 3.14) | Core runtime environment |
| **PortAudio** | `>= 19` (optional) | Required for microphone audio input (`akande[mic]`) |
| **FFmpeg** | Any modern release (optional) | Required for MP3 / non-WAV audio transcoding |
| **Platforms** | Linux (x86_64, aarch64), macOS (Intel, Apple Silicon), Windows | Platform-agnostic Python package |

---

## Quick Start

```python
import os
from akande.pipeline import run_pipeline

os.environ["LLM_PROVIDER"] = (
    "ollama"  # or openai, anthropic, google, claude_cli, etc.
)

result = run_pipeline(
    "Provide a morning executive briefing on market trends."
)
print(f"Summary: {result.summary}")
print(f"Response: {result.response}")
```

This runs the end-to-end Àkàndé pipeline: intent classification, safety wrapping, provider execution, and optional speech synthesis.

---

## The Àkàndé ecosystem

Àkàndé provides a complete voice-first executive briefing stack across command-line, graphical terminal, REST, and protocol interfaces:

| Component | Purpose | Use case |
| :--- | :--- | :--- |
| `akande.pipeline` | Core orchestration pipeline | Intent classification, safety envelopes, tool dispatch |
| `akande.server` | REST and SSE streaming server | Web-based clients and HTTP streaming integrations |
| `akande.tui` | Bubble Tea interactive terminal UI | Full-screen interactive terminal workflow |
| `akande.mcp` | Model Context Protocol client and server | Exposing Àkàndé tools to Claude Desktop, Cursor, Continue |

---

## Capabilities at a glance

| Area | Capability | Status |
| :--- | :--- | :--- |
| **Providers** | 11 LLM providers (OpenAI, Anthropic, Google, Claude CLI, Mistral, Cohere, etc.) | Production |
| **Speech-to-Text** | SpeechRecognition and Faster-Whisper backends | Production |
| **Text-to-Speech** | gTTS and local Kokoro-82M ONNX offline synthesis | Production |
| **Safety & Audit** | Input sanitization, safety envelopes, cryptographically verifiable PDF audits | Production |
| **Compliance** | EU AI Act Article 50 transparency and AudioSeal audio watermarking | Production |

---

## Ecosystem comparison

| Project | Self-Hosted | Multi-Provider | Voice STT/TTS | Article 50 Audit |
| :--- | :---: | :---: | :---: | :---: |
| **Àkàndé** | Yes | 11 providers | Yes (Native) | Yes (Cryptographic) |
| **Open-WebUI** | Yes | Yes | Partial | No |
| **LocalAI** | Yes | Local only | Yes | No |

See [`docs/COMPARISON.md`](docs/COMPARISON.md) for the evidence and complete matrix.

---

## Benchmarks

| Scenario | Result | Environment |
| :--- | ---: | :--- |
| Pipeline dispatch overhead | `< 1.2 ms` | Apple Silicon M3 / Python 3.13 |
| Watermark verification latency | `< 18 ms` | Apple Silicon M3 / 1s audio |
| Audio sanitization & safety wrapping | `< 0.3 ms` | Ubuntu 24.04 / Python 3.12 |

See [`docs/BENCHMARKS.md`](docs/BENCHMARKS.md) for methodology and full results.

---

## Features

- **11 LLM Providers** : Switch between OpenAI, Anthropic, Google Gemini, Claude Code CLI, Mistral, Cohere, Groq, Ollama, LM Studio, Azure, and Codex CLI.
- **Safety Envelope** : Strict transcript sanitization, control character stripping, length clamping, and `<user_input>` boundary envelopes.
- **SSRF Prevention** : Built-in host validation restricting loopbacks, private RFC 1918 subnets, link-local addresses, and cloud metadata services.
- **Regulatory Transparency** : Full EU AI Act Article 50 compliance with machine-readable audit manifests and AudioSeal watermarking.

---

## Configuration

Set configuration through environment variables or `.env` files:

```bash
# Provider selection
export LLM_PROVIDER=openai  # anthropic, google, ollama, claude_cli, etc.

# Operational profile
export AKANDE_PROFILE=eu    # eu (strict compliance) or default

# Audio configuration
export AKANDE_TTS=kokoro    # gtts or kokoro
export AKANDE_STT=sr        # sr or faster_whisper
```

---

## Examples

Runnable examples demonstrating features:

- [`examples/basic_briefing.py`](examples/basic_briefing.py) : Simple 10-line text briefing.
- [`examples/voice_interaction.py`](examples/voice_interaction.py) : Interactive microphone capture and voice synthesis.
- [`examples/mcp_server.py`](examples/mcp_server.py) : Connecting Àkàndé tools to an MCP host.

---

## When not to use Àkàndé

- **Raw conversational chatbot** : Àkàndé is optimized for structured, factual executive briefings and action synthesis rather than open-ended chit-chat.
- **Ultra-low-latency telephony** : Real-time sub-100ms voice agents require specialized WebRTC infrastructure; Àkàndé targets structured turn-taking.

---

## Development

```bash
uv venv
uv pip install -e ".[all,dev]" mcp
uv run --extra dev pytest
uv run --extra dev ruff check .
```

All contributions must pass the verification gates (pytest with >= 95% coverage, ruff, mypy, bandit, pip-audit).

---

## Security

Àkàndé enforces security best practices across input validation, network tools, and credential handling:
- Private IP and SSRF rejection on external fetch tools.
- Strict input sanitization and delimiter escaping on speech transcripts.
- Cryptographically signed audit manifests with SHA-256 sidecars.

Report vulnerabilities according to [`SECURITY.md`](SECURITY.md).

---

## Documentation

- [User Guide](docs/README.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Policies & Gates](docs/POLICIES.md)
- [Development Guide](DEVELOPMENT.md)

---

## Stability guarantees

Àkàndé adheres to strict Semantic Versioning:
- **Patch releases (0.0.x -> 0.0.y)** : Backwards-compatible bug fixes and security patches.
- **Breaking changes** : Never introduced in patch releases. Deprecations documented at least one minor iteration in advance.

---

## License

Dual-licensed under Apache-2.0 OR MIT at your option:
- [Apache License, Version 2.0](LICENSE-APACHE)
- [MIT License](LICENSE-MIT)
