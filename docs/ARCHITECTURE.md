<!-- SPDX-License-Identifier: Apache-2.0 OR MIT -->

# Architecture of Àkàndé

Àkàndé is designed as a modular, provider-agnostic, voice-first executive briefing stack. This document details its subsystem design, data flow, and security boundaries.

## Architecture Overview

```
                                  +-------------------+
                                  |    User Client    |
                                  | (TUI / CLI / Web) |
                                  +---------+---------+
                                            |
                                            v
+-----------------------------------------------------------------------------------+
|                                  Àkàndé Pipeline                                  |
|                                                                                   |
|  +-----------------------+   +----------------------+   +----------------------+  |
|  | Transcript / Input    |-->| Safety Boundary      |-->| Intent Classifier &  |  |
|  | Sanitization          |   | Wrapping             |   | Skill Router         |  |
|  +-----------------------+   +----------------------+   +-----------+----------+  |
|                                                                     |             |
|                                                                     v             |
|  +-----------------------+   +----------------------+   +----------------------+  |
|  | Machine-Readable      |<--| Cryptographic        |<--| Provider Dispatch    |  |
|  | Audit Manifest        |   | Watermarking (TTS)   |   | (11 LLM Backends)    |  |
|  +-----------------------+   +----------------------+   +----------------------+  |
+-----------------------------------------------------------------------------------+
```

## Subsystem Breakdown

### 1. Ingestion and Sanitization (`akande.safety`, `akande.server`)
Before any text reaches downstream processing:
- Control characters and invisible Unicode sequences are stripped.
- Whitespace is collapsed and normalized.
- Transcripts are strictly clamped to maximum token/character lengths.
- Prompts are encapsulated inside `<user_input>` boundary tags to prevent prompt injection and instruction hijacking.

### 2. Provider Abstraction (`akande.providers`)
The provider layer abstracts 11 distinct LLM inference engines behind a uniform `LLMProvider` interface:
- **Cloud Providers**: OpenAI, Anthropic, Google Gemini, Mistral, Cohere, Groq, Azure OpenAI.
- **Local Providers**: Ollama, LM Studio.
- **CLI Proxies**: Claude Code CLI (`claude_cli`), GitHub Copilot CLI, OpenAI Codex CLI.
Every provider supports both synchronous execution and chunked token streaming.

### 3. Audio Processing Stack (`akande.stt`, `akande.tts`, `akande.s2s`)
- **Speech-to-Text**: Pluggable backends supporting SpeechRecognition (online/system) and Faster-Whisper (local offline models).
- **Text-to-Speech**: Modular backends including offline Kokoro-82M ONNX synthesis and gTTS.
- **Speech-to-Speech**: Low-latency duplex pipelines integrating OpenAI Realtime API and Gemini Live.

### 4. Network and Tool Security (`akande.tools`)
- **SSRF Prevention**: All external network requests via `fetch_url` validate destination IP addresses, barring loopback (`127.0.0.0/8`, `::1`), private RFC 1918 subnets (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`), link-local spaces (`169.254.0.0/16`), and cloud metadata APIs.
- **Skill Sandboxing**: Skills require explicit user consent when performing unauthenticated web queries.

### 5. Compliance & Auditability (`akande.audit`, `akande.watermark`)
- **EU AI Act Article 50**: Machine-readable JSON metadata sidecars accompany generated briefing artifacts.
- **Audit Signing**: Sidecars are cryptographically hashed (SHA-256) and signed with Ed25519 keypairs.
- **Watermarking**: Synthesized audio passes through AudioSeal encoding to ensure provenance verification.
