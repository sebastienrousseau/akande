<!-- markdownlint-disable MD033 MD041 -->

<img
src="https://kura.pro/akande/images/logos/akande.webp"
align="right"
alt="Akande Voice Assistant Logo"
height="261"
width="261"
/>

<!-- markdownlint-enable MD033 MD041 -->

# Àkàndé

![Banner for Àkàndé - Voice Assistant][banner]

Àkàndé is a self-hosted, provider-agnostic voice assistant that delivers
structured executive briefings from any of 10 supported LLM providers.
Ask a question by voice or text; receive a concise
Overview / Solution / Conclusion / Recommendations briefing with
automatic PDF and CSV artefact generation. Run it against OpenAI, or
keep your data entirely private with Ollama or LM Studio on your own
hardware.

The name "Àkàndé" (Yoruba: "firstborn") signifies a pioneering approach
to voice-driven intelligence briefings.

![divider][divider]

## Why Àkàndé?

Ask a question. Get a structured briefing. Keep your data.

That is the entire workflow. Voice, text, or web -- Àkàndé listens,
queries the LLM of your choice, and delivers a four-section executive
briefing: Overview, Solution, Conclusion, Recommendations. PDF and CSV
artefacts are generated automatically.

No framework to learn. No output parsing to build. No provider lock-in
to accept.

Ten LLM providers -- including fully private local inference through
Ollama and LM Studio -- all behind one environment variable. Your
hardware. Your models. Your data.

Every other tool gives you the engine and expects you to build the car.
Àkàndé hands you the keys. This is how AI assistants should have always
worked.

![divider][divider]

## Who is Àkàndé for?

**Python developers** who deploy it: clone, configure a provider, and
run. Àkàndé is a standard Python package with a CLI entry point, a
CherryPy web server mode, and 161 tests.

**End users and executives** who interact with it: speak or type a
question and receive a structured briefing read aloud and saved as
PDF/CSV. No technical knowledge required once deployed.

![divider][divider]

## Quick Start

### Prerequisites

- Python 3.9+
- PortAudio (for microphone input):
  Ubuntu/Debian `sudo apt install portaudio19-dev`,
  macOS `brew install portaudio`
- ffmpeg (for audio conversion):
  Ubuntu/Debian `sudo apt install ffmpeg`,
  macOS `brew install ffmpeg`

### Installation

```bash
git clone https://github.com/sebastienrousseau/akande
cd akande
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env: set OPENAI_API_KEY=sk-your-key-here

python -m akande
```

Select option **2** ("Ask a question"), type your query, and receive a
structured briefing.

![divider][divider]

## Provider Configuration

Set `LLM_PROVIDER` in your `.env` file. Install extras for non-OpenAI
providers.

| Provider | `LLM_PROVIDER` | Required env vars | Install extras | Default model |
|---|---|---|---|---|
| OpenAI | `openai` | `OPENAI_API_KEY` | *(included)* | `gpt-3.5-turbo` |
| Anthropic | `anthropic` | `ANTHROPIC_API_KEY` | `pip install akande[anthropic]` | `claude-3-haiku-20240307` |
| Google Gemini | `google` | `GOOGLE_API_KEY` | `pip install akande[google]` | `gemini-pro` |
| Ollama | `ollama` | `OLLAMA_HOST` | *(included)* | `llama3` |
| Azure OpenAI | `azure_openai` | `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_ENDPOINT` | *(included)* | `gpt-35-turbo` |
| Mistral | `mistral` | `MISTRAL_API_KEY` | `pip install akande[mistral]` | `mistral-small-latest` |
| Cohere | `cohere` | `COHERE_API_KEY` | `pip install akande[cohere]` | `command-r` |
| Hugging Face | `huggingface` | `HUGGINGFACE_API_KEY` | `pip install akande[huggingface]` | `mistralai/Mistral-7B-Instruct-v0.2` |
| Groq | `groq` | `GROQ_API_KEY` | *(included)* | `llama3-8b-8192` |
| LM Studio | `lmstudio` | `LMSTUDIO_HOST` | *(included)* | `local-model` |

To install all optional provider SDKs: `pip install akande[all]`

![divider][divider]

## Interaction Modes

Àkàndé presents a CLI menu with four options:

1. **Use voice** -- speak your question via microphone; response is read
   aloud
2. **Ask a question** -- type your question; response is printed and
   read aloud
3. **Start server** -- launches a web UI at `http://127.0.0.1:8080`
   with voice and text input
4. **Stop** -- exits the assistant

![divider][divider]

## Example Interaction

**Question:** "What is quantitative easing?"

> **Overview**
> Quantitative easing (QE) is a monetary policy tool used by central
> banks to stimulate economic activity when conventional interest rate
> cuts are insufficient.
>
> **Solution**
> - Central banks purchase government bonds and other securities to
>   inject money into the economy
> - This lowers long-term interest rates, encouraging borrowing and
>   investment
> - QE increases the money supply without printing physical currency
>
> **Conclusion**
> QE can stabilise financial markets during crises but carries risks of
> asset bubbles and currency devaluation.
>
> **Recommendations**
> - Monitor inflation indicators alongside QE announcements
> - Consider the impact on bond yields for portfolio decisions

Each response is automatically saved as a timestamped PDF and CSV in the
output directory.

![divider][divider]

## Troubleshooting

| Problem | Cause | Fix |
|---|---|---|
| `Could not find PyAudio` | PortAudio missing | Ubuntu: `sudo apt install portaudio19-dev`. macOS: `brew install portaudio`. Then `pip install pyaudio`. |
| `ffmpeg not found` | ffmpeg not installed | Ubuntu: `sudo apt install ffmpeg`. macOS: `brew install ffmpeg`. |
| Microphone not detected | OS permissions | Grant microphone access in system settings. |
| `ModuleNotFoundError: No module named 'anthropic'` | Provider SDK not installed | `pip install akande[anthropic]`. See the provider table above. |
| `Invalid or missing OPENAI_API_KEY` | Key not set or malformed | Ensure `.env` contains a valid `sk-` prefixed key. |

![divider][divider]

## Roadmap

- Streaming responses for reduced time-to-first-token
- Conversation memory with multi-turn context
- Markdown and HTML briefing output formats
- Plugin system for domain-specific briefing templates
- Docker image for single-command deployment

![divider][divider]

## Trust

- **161 tests** covering providers, caching, services, server, and
  utilities
- **Apache 2.0 licence** -- permissive, enterprise-friendly
- **Euxis-audited** architecture and security posture

![divider][divider]

## Contributing

Pull requests are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for
guidelines.

![divider][divider]

## License

This project is licensed under the Apache Software License -- see the
[LICENSE](LICENSE) file for details.

![divider][divider]

[divider]: https://kura.pro/common/images/elements/divider.svg "Divider"
[banner]: https://kura.pro/akande/images/titles/title-akande.webp "Banner for Àkàndé - Voice Assistant"
