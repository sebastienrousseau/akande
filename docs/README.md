<!-- SPDX-License-Identifier: Apache-2.0 OR MIT -->

# Àkàndé User Guide

Comprehensive documentation on configuring, running, and extending Àkàndé.

## Table of Contents

- [Installation](#installation)
- [Quick Start](#quick-start)
- [Provider Setup](#provider-setup)
- [Interaction Modes](#interaction-modes)
- [Subcommands](#subcommands)
- [Model Context Protocol (MCP)](#model-context-protocol-mcp)

---

## Installation

### Standard Core Installation

```bash
pip install akande
```

### Optional Extras

- **Full Provider Suite**: `pip install "akande[all]"`
- **Microphone Voice Capture**: `pip install "akande[mic]"` (requires PortAudio system library)
- **Model Context Protocol**: `pip install "akande[mcp]"`
- **Watermark Verification**: `pip install "akande[watermark]"`
- **Development Tooling**: `pip install "akande[dev]"`

---

## Quick Start

Execute a programmatic briefing:

```python
import os
from akande.pipeline import run_pipeline

os.environ["LLM_PROVIDER"] = "ollama"
briefing = run_pipeline("Prepare a morning market summary.")
print(briefing.response)
```

---

## Provider Setup

Set your preferred provider using `LLM_PROVIDER`:

| Provider | Env Value | Required Credentials | Notes |
| :--- | :--- | :--- | :--- |
| **OpenAI** | `openai` | `OPENAI_API_KEY` | GPT-4o / GPT-4o-mini |
| **Anthropic** | `anthropic` | `ANTHROPIC_API_KEY` | Claude 3.5 Sonnet |
| **Claude Code CLI** | `claude_cli` | None | Reuses active `claude` CLI login |
| **Google Gemini** | `google` | `GEMINI_API_KEY` | Gemini 1.5 Pro / Flash |
| **Ollama** | `ollama` | Optional `OLLAMA_HOST` | Local offline inference |
| **LM Studio** | `lmstudio` | Optional `LMSTUDIO_HOST` | Local offline inference |

---

## Interaction Modes

1. **Bubble Tea Terminal TUI**:
   ```bash
   akande
   ```
2. **Classic CLI Menu**:
   ```bash
   akande --classic
   ```
3. **Web Server with SSE Streaming**:
   ```bash
   akande-server --port 8080
   ```

---

## Subcommands

- **Data Management**:
  ```bash
  akande data export --user alice --output alice.json
  akande data delete --user alice --yes
  ```
- **Audit Verification**:
  ```bash
  akande verify-audit path/to/briefing.audit.json
  ```
- **MCP Integration**:
  ```bash
  akande mcp serve
  ```
