# ADR-001: Multi-Provider LLM Abstraction

## Status
Accepted

## Date
2026-02-01

## Context
Akande is an AI voice assistant currently hardcoded to use OpenAI as
its sole LLM provider. Users need the ability to choose between
multiple providers for reasons of cost, latency, data privacy (local
inference with Ollama/LM Studio), and vendor independence.

## Decision
Adopt an adapter pattern with a frozen abstract base class
(`LLMProvider`) and a singleton `ProviderRegistry` for runtime
provider resolution.

### Architecture

```
App (Akande CLI / CherryPy Server)
        |
    AI Core (services.py: SYSTEM_PROMPT, Akande.generate_response)
        |
    Provider Adapter Interface (providers/base.py: LLMProvider ABC)
        |
 +----------+----------+---------+---------+-----------+
 | OpenAI   | Anthropic| Google  | Ollama  | Azure OAI |
 | Mistral  | Cohere   | HF Inf  | Groq    | LM Studio |
 +----------+----------+---------+---------+-----------+
```

### Provider Categories

1. **OpenAI-compatible** (shared `openai` SDK, different base_url):
   OpenAI, Azure OpenAI, Ollama, LM Studio, Groq

2. **Native SDK** (provider-specific client libraries):
   Anthropic, Google Gemini, Mistral, Cohere, Hugging Face

### Key Design Decisions

- **Lazy imports**: Each provider imports its SDK inside `__init__`,
  not at module level. Only the configured provider's dependencies
  are loaded.

- **OpenAI-compatible base class**: Five providers share a common
  base (`OpenAICompatProvider`) that configures `openai.OpenAI` with
  provider-specific `base_url` and `api_key`.

- **Response normalisation**: Native SDK providers wrap their
  responses in a `ProviderResponse` dataclass with a
  `.choices[0].message.content` interface matching OpenAI's format.

- **Frozen ABC**: The `LLMProvider` interface is frozen after this
  ADR. New methods require a new ABC version.

## Consequences

### Positive
- Adding an OpenAI-compatible provider requires ~15 lines of code
- Adding a native SDK provider requires ~80-100 lines
- No runtime overhead (registry lookup is O(1) at startup)
- Full backward compatibility with existing OpenAI-only usage

### Negative
- One-way door: the ABC interface cannot change without a breaking
  version bump
- Native SDK providers must implement response normalisation
- Optional dependencies increase the surface area for supply-chain
  risk (mitigated by lazy imports and extras_require)

### Risks
- Provider SDK breaking changes require adapter updates
- Local providers (Ollama, LM Studio) require users to run a
  separate service
