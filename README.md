<!-- markdownlint-disable MD033 MD041 -->

<p align="center">
  <img src="https://kura.pro/akande/images/logos/akande.webp" alt="Àkàndé logo" width="160" />
</p>

<h1 align="center">Àkàndé</h1>

<p align="center">
  A self-hosted, provider-agnostic voice assistant that delivers structured
  executive briefings from any of ten LLM providers — including fully private
  local inference via Ollama and LM Studio.
</p>

<p align="center">
  <a href="https://github.com/sebastienrousseau/akande/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/sebastienrousseau/akande/ci.yml?branch=main&style=for-the-badge&label=CI&logo=github" alt="CI" /></a>
  <a href="https://github.com/sebastienrousseau/akande/actions/workflows/regression.yml"><img src="https://img.shields.io/github/actions/workflow/status/sebastienrousseau/akande/regression.yml?branch=main&style=for-the-badge&label=Regression&logo=github" alt="Regression" /></a>
  <a href="https://pypi.org/project/akande/"><img src="https://img.shields.io/pypi/v/akande?style=for-the-badge&color=fc8d62&logo=pypi&logoColor=white" alt="PyPI" /></a>
  <a href="https://pypi.org/project/akande/"><img src="https://img.shields.io/pypi/pyversions/akande?style=for-the-badge&logo=python&logoColor=white" alt="Python versions" /></a>
  <a href="https://github.com/sebastienrousseau/akande/blob/main/LICENSE-APACHE"><img src="https://img.shields.io/badge/license-Apache--2.0%20OR%20MIT-blue?style=for-the-badge" alt="License" /></a>
  <a href="https://scorecard.dev/viewer/?uri=github.com/sebastienrousseau/akande"><img src="https://img.shields.io/ossf-scorecard/github.com/sebastienrousseau/akande?style=for-the-badge&label=OpenSSF%20Scorecard&logo=openssf" alt="OpenSSF Scorecard" /></a>
</p>

---

## Contents

**Getting started**

- [Install](#install) — PyPI, source, system dependencies
- [Quick Start](#quick-start) — voice briefing in ten lines
- [Use as a library](#use-as-a-library) — programmatic API

**Surface**

- [Provider configuration](#provider-configuration) — ten providers behind one env var
- [Profiles and modes](#profiles-and-modes) — `AKANDE_PROFILE` and `AKANDE_MODE`
- [Interaction modes](#interaction-modes) — TUI, classic CLI, web server, MCP
- [Subcommands](#subcommands) — `data`, `verify-audit`, `mcp`, `install-local`, `skill`
- [Skills](#skills) — briefing, web search, weather, finance + consent policy
- [Model Context Protocol](#model-context-protocol) — serve and consume MCP

**Operational**

- [Compliance](#compliance) — EU AI Act Article 50 controls
- [Troubleshooting](#troubleshooting)
- [Trust](#trust) — test count, coverage, security gates
- [Development](#development)
- [License](#license)

---

## Install

### Prerequisites

| Dependency | Why | Ubuntu / Debian | macOS |
|---|---|---|---|
| Python 3.10+ | Runtime | `sudo apt install python3.12 python3.12-venv` | `brew install python@3.12` |
| `portaudio` *(optional)* | Microphone capture (`[mic]` extra) | `sudo apt install portaudio19-dev` | `brew install portaudio` |
| `ffmpeg` | Audio decoding | `sudo apt install ffmpeg` | `brew install ffmpeg` |

### From PyPI

```bash
# Core install — provider SDKs and mic capture are optional extras.
pip install akande

# Full kit: every provider + microphone + MCP.
pip install "akande[all,mic,mcp]"
```

### From source

```bash
git clone https://github.com/sebastienrousseau/akande
cd akande
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"        # bundles every test-relevant extra
```

### Extras index

| Extra | Pulls in | Enables |
|---|---|---|
| `mic` | `pyaudio` | Microphone capture (requires PortAudio system headers) |
| `anthropic` / `google` / `mistral` / `cohere` / `huggingface` / `groq` | the matching SDK | The corresponding `LLM_PROVIDER` value |
| `offline-tts` | `pyttsx4` | Offline TTS fallback |
| `tts-local` | `kokoro-onnx` | Local Kokoro-82M TTS (`AKANDE_TTS=kokoro`) |
| `watermark` | `audioseal`, `torch` | AudioSeal voice watermarking (Article 50 §2) |
| `redact` | `presidio-analyzer` | Higher-recall PII redaction in the cache |
| `memory` | `mem0ai` | Long-term memory façade |
| `mcp` | `mcp` | Run / consume Model Context Protocol servers |
| `redis` | `redis` | Distributed rate limiter for the web server |
| `all` | every provider SDK + `pyttsx4` | Provider-agnostic deployments |
| `dev` | testing + lint + audit + every provider SDK + `mcp` | Local development |

---

## Quick Start

```bash
# 1. Install the core + the mic extra.
pip install "akande[mic]"

# 2. Point at a provider.
export LLM_PROVIDER=openai
export OPENAI_API_KEY=sk-your-key-here

# 3. Launch the TUI.
akande
```

The TUI accepts spoken or typed questions and renders the briefing as it
streams in. PDF and CSV artefacts are written to a date-keyed output
directory on every answered question.

### Use as a library

```python
"""Ask Àkàndé a question programmatically."""
import asyncio

from akande.akande import Akande
from akande.providers import get_provider


async def main() -> None:
    # 1. Pick any of the ten configured providers by name.
    provider = get_provider("openai")             # honours $OPENAI_API_KEY
    akande = Akande(openai_service=provider)

    # 2. Ask a question.  The four-section briefing comes back as plain text.
    question = "What is quantitative easing?"
    response = await akande.openai_service.generate_response(
        user_prompt=question,
        system_prompt="You are an executive briefing assistant.",
        model="gpt-4o-mini",
    )

    # 3. Print the structured briefing.  `choices[0].message.content` follows
    # the OpenAI-shaped response envelope used by every provider.
    print(response.choices[0].message.content)


if __name__ == "__main__":
    asyncio.run(main())
```

---

## Provider configuration

Set `LLM_PROVIDER` in your environment (or `.env` file). Each provider reads
its own credentials from environment variables.

| Provider | `LLM_PROVIDER` | Required env vars | Install | Default model |
|---|---|---|---|---|
| OpenAI | `openai` | `OPENAI_API_KEY` | *(included)* | `gpt-3.5-turbo`¹ |
| Anthropic | `anthropic` | `ANTHROPIC_API_KEY` | `pip install akande[anthropic]` | `claude-3-haiku-20240307` |
| Google Gemini | `google` | `GOOGLE_API_KEY` | `pip install akande[google]` | `gemini-pro` |
| Mistral | `mistral` | `MISTRAL_API_KEY` | `pip install akande[mistral]` | `mistral-small-latest` |
| Cohere | `cohere` | `COHERE_API_KEY` | `pip install akande[cohere]` | `command-r` |
| Hugging Face | `huggingface` | `HUGGINGFACE_API_KEY` | `pip install akande[huggingface]` | `mistralai/Mistral-7B-Instruct-v0.2` |
| Groq | `groq` | `GROQ_API_KEY` | `pip install akande[groq]` | `llama3-8b-8192` |
| Azure OpenAI | `azure_openai` | `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_ENDPOINT` | *(included)* | `gpt-35-turbo` |
| Ollama | `ollama` | `OLLAMA_HOST` *(optional)* | *(included)* | `llama3` |
| LM Studio | `lmstudio` | `LMSTUDIO_HOST` *(optional)* | *(included)* | `local-model` |

> ¹ Override per-call with the `model` argument or globally with
> `OPENAI_DEFAULT_MODEL`.

Install every provider SDK at once with `pip install akande[all]`.

---

## Profiles and modes

Àkàndé exposes two orthogonal sovereignty switches.

`AKANDE_PROFILE` selects the compliance posture:

| Profile | EU residency | Audio watermark | Audit signing | Telemetry opt-in |
|---|---|---|---|---|
| `local` *(default)* | — | off | off | off |
| `eu` | enforced | on | on | off |
| `strict` | enforced | on | on | off |
| `internal` | — | on | on | on (opt-in only) |

`AKANDE_MODE` selects the network posture:

| Mode | Provider gate | Cache writes |
|---|---|---|
| `online` *(default)* | any provider | enabled |
| `offline` | `ollama` or `lmstudio` only | enabled |

```bash
# EU-residency-aware cloud setup
export AKANDE_PROFILE=eu AKANDE_MODE=online

# Fully air-gapped local stack
export AKANDE_PROFILE=strict AKANDE_MODE=offline LLM_PROVIDER=ollama
```

---

## Interaction modes

| Mode | How to launch | What you get |
|---|---|---|
| **TUI** *(default)* | `akande` | Textual chat UI with streaming, voice toggle, history, export |
| **Classic CLI** | `akande --classic` | Numbered menu: voice, text, server, quit |
| **Web server** | `akande` → start server (or library `Akande.start_server()`) | CherryPy server at `http://127.0.0.1:8080` with SSE briefing endpoint |
| **MCP server** | `akande mcp serve` | Expose Àkàndé as MCP tools (Claude Desktop, Cursor, Continue) |
| **Library** | `from akande.akande import Akande` | Programmatic embedding |

---

## Subcommands

```bash
akande --help                  # top-level help
akande --version               # installed version

# GDPR data subject controls (export / delete)
akande data export --user alice --output alice.json
akande data delete --user alice --yes

# Audit verification — Ed25519-signed briefing sidecars
akande verify-audit  path/to/briefing.audit.json
akande verify-pdf    path/to/briefing.pdf
akande verify-watermark path/to/briefing.mp3 --threshold 0.5

# Model Context Protocol
akande mcp serve                # stdio MCP server (Claude Desktop ready)
akande mcp serve --http         # streamable HTTP transport
akande mcp list                 # list configured upstream servers
akande mcp list <server>        # introspect a server's tools

# One-shot fully-offline bootstrap
akande install-local --model llama3.1 --env-path .env

# Skill management
akande skill list
akande skill enable web_search
akande skill consent web_search
akande skill revoke web_search
```

---

## Skills

Skills are specialised handlers the router picks over a generic LLM call.
Five ship in the box; third-party skills register via the
`akande.skills` entry-point group.

| Skill | Match | Consent required | Offline-safe |
|---|---|---|---|
| `briefing` | default | no | yes |
| `web_search` | `search`, `look up …`, `find …` | yes | no |
| `weather` | `weather in …`, `forecast …` | no | no |
| `finance` | `price of …`, `ticker …` | no | no |
| `policy` *(gate)* | always — enforces consent | n/a | yes |

```python
"""Register a third-party skill via the entry-point group."""
# pyproject.toml
# [project.entry-points."akande.skills"]
# my_skill = "my_package.skill:MySkill"

from akande.skills.base import Skill, SkillMeta, Intent, SkillContext, SkillResult


class MySkill(Skill):
    @property
    def meta(self) -> SkillMeta:
        return SkillMeta(
            name="my_skill",
            description="One-line description of what this skill does.",
            requires_consent=True,
        )

    def match(self, text: str) -> Intent | None:
        if text.lower().startswith("my-skill:"):
            return Intent(name="my_skill", raw_text=text)
        return None

    def handle(self, intent: Intent, ctx: SkillContext) -> SkillResult:
        return SkillResult(content=f"Handled: {intent.raw_text}")
```

---

## Model Context Protocol

Àkàndé can serve **and** consume MCP. The server exposes the briefing,
audit, and skill surface as MCP tools; the client introspects upstream
servers configured in `~/.akande/mcp.json`.

```bash
# Serve over stdio for Claude Desktop / Cursor / Continue.
akande mcp serve

# Or streamable HTTP for HTTP-only hosts.
akande mcp serve --http
```

Claude Desktop drop-in (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "akande": {
      "command": "akande",
      "args": ["mcp", "serve"]
    }
  }
}
```

---

## Compliance

Àkàndé ships the controls required by EU AI Act Article 50 (in force
2026-08-02) out of the box when `AKANDE_PROFILE=eu` (or `strict`):

- **AI disclosure** — every briefing carries a machine-readable disclosure
  block (`akande.disclosure`)
- **AudioSeal watermark** — synthesised audio is watermarked when the
  `[watermark]` extra is installed; absence is logged but never blocks
- **Ed25519-signed audit sidecars** — every PDF + CSV is paired with a
  `.audit.json` signed at write time; `akande verify-audit` re-verifies
- **GDPR data export / delete** — `akande data export|delete` against
  the SQLite conversation store
- **Consent log** — voice-cloning prompts require explicit consent
  recorded in the audit chain

---

## Troubleshooting

| Problem | Cause | Fix |
|---|---|---|
| `Could not find PyAudio` | PortAudio system headers missing | Ubuntu: `sudo apt install portaudio19-dev`. macOS: `brew install portaudio`. Then `pip install akande[mic]`. |
| `ffmpeg not found` | ffmpeg not installed | Ubuntu: `sudo apt install ffmpeg`. macOS: `brew install ffmpeg`. |
| Microphone not detected | OS permissions | Grant microphone access in system settings. |
| `ModuleNotFoundError: No module named 'anthropic'` | Provider SDK not installed | `pip install akande[anthropic]` (or the relevant provider extra). |
| `Invalid or missing OPENAI_API_KEY` | Key not set or malformed | Ensure your environment or `.env` contains a valid `sk-` prefixed key. |
| `AKANDE_MODE=offline forbids provider openai` | Offline mode allows only local providers | Set `LLM_PROVIDER=ollama` or `LLM_PROVIDER=lmstudio`, or switch back to `AKANDE_MODE=online`. |

---

## Trust

- **785 tests** + **95 % line coverage** in CI on every push and pull
  request, on Python 3.10 / 3.11 / 3.12
- **Quality gates**: ruff (lint + format), mypy (strict islands on the
  provider surface), bandit (SAST), pip-audit (vulnerable-deps scan) —
  all blocking
- **Fresh-install regression matrix** (Ubuntu × 3.10/3.11/3.12 +
  macOS × 3.12) reproduces the user install path on every push
- **Security posture** documented in [SECURITY.md](SECURITY.md): CSP
  nonces, custom-header CSRF, per-IP rate limiting (in-memory or Redis),
  CSV-formula injection prevention, filename sanitisation, IP hashing
  in logs

---

## Development

```bash
git clone https://github.com/sebastienrousseau/akande
cd akande
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Quality gates (mirror CI)
ruff check . && ruff format --check .
mypy akande
pytest -q                # uses the [pytest] cov gate (95 %)
bandit -r akande
pip-audit

# Fresh-install regression on this machine
./scripts/regression.sh
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full development loop.

---

## License

Dual-licensed under the Apache License, Version 2.0 and the MIT License.
See [LICENSE-APACHE](LICENSE-APACHE) and [LICENSE-MIT](LICENSE-MIT) for
the full text. You may pick whichever fits your project.
