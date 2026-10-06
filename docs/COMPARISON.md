<!-- SPDX-License-Identifier: Apache-2.0 OR MIT -->

# Ecosystem Comparison

This document provides a comparative analysis of Àkàndé against alternative open-source and self-hosted AI assistant platforms.

## Feature Matrix

| Feature | Àkàndé | Open-WebUI | LocalAI | Ollama CLI | LibreChat |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Primary Focus** | Executive Briefings & Voice | Chat UI | LLM Inference API | Local Model Runner | Multi-Model Chat |
| **Self-Hosted** | Yes | Yes | Yes | Yes | Yes |
| **LLM Providers** | 11 providers | Many (OpenAI API) | Local + OpenAI | Local models | Many (OpenAI API) |
| **Native Voice STT** | Yes (SR + Whisper) | Browser Web Speech | Yes (Whisper) | No | Browser Web Speech |
| **Native Voice TTS** | Yes (Kokoro + gTTS) | Web Speech / OpenAI | Yes (Piper / TTS) | No | Web Speech / OpenAI |
| **Offline Voice Stack** | Yes (ONNX Kokoro) | No (requires server) | Yes | No | No |
| **No-API-Key Path** | Yes (`claude_cli`) | No | Yes (local) | Yes (local) | No |
| **Safety Boundary Envelopes** | Yes (`<user_input>`) | No | No | No | Moderation API |
| **Input Sanitization** | Yes (Control chars, length) | Minimal | Minimal | None | Basic |
| **SSRF Prevention** | Yes (RFC 1918, metadata) | No | No | N/A | Basic |
| **EU AI Act Art. 50 Audits** | Yes (Machine-readable) | No | No | No | No |
| **Cryptographic Signatures** | Yes (Ed25519 sidecars) | No | No | No | No |
| **Audio Watermarking** | Yes (AudioSeal) | No | No | No | No |
| **MCP Support** | Server + Client | Tools integration | Function calling | No | MCP Plugin |
| **Interactive Terminal TUI** | Yes (Bubble Tea) | No | No | Basic CLI | No |
| **Streaming Pipeline** | Yes (SSE + chunks) | WebSocket / SSE | SSE | Streaming stdout | SSE |
| **GDPR Export / Delete** | Yes (`akande data`) | Partial | No | No | User management |

## Key Differentiators

### 1. Structured Briefings vs. Open-Ended Chat
Àkàndé is engineered specifically for concise, structured executive summaries and action items. Rather than open-ended conversational drift, pipelines enforce strict intent classification, focused skill routing, and deterministic output structures.

### 2. Comprehensive Security Envelopes
User audio and text inputs are sanitized, length-clamped, and wrapped in strict safety boundaries before passing to any LLM provider. Outbound network tools enforce strict SSRF protections against private subnets (RFC 1918), loopback addresses, link-local scopes, and cloud metadata endpoints (e.g., `169.254.169.254`).

### 3. Regulatory Transparency and Watermarking
To satisfy EU AI Act Article 50 requirements, Àkàndé generates machine-readable disclosure manifests and cryptographically signs briefing sidecars with Ed25519 signatures. Synthesized audio optionally carries imperceptible AudioSeal watermarks for provenance tracking.

### 4. Zero-API-Key Local CLI Mode
With `LLM_PROVIDER=claude_cli`, Àkàndé integrates with existing local Claude Code CLI authentication sessions without requiring standalone API keys, rates, or credential exposures.
