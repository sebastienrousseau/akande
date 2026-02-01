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

Àkàndé is an advanced voice assistant built in Python, supporting 10 LLM providers for natural language understanding and response generation. Àkàndé includes a caching mechanism for efficient response retrieval and the ability to generate PDF summaries of interactions, making it ideal for both personal assistance and executive briefing purposes.

![divider][divider]

## Features

- **Multi-Provider LLM Support**: Choose from 10 providers — OpenAI, Anthropic, Google Gemini, Ollama, Azure OpenAI, Mistral, Cohere, Hugging Face, Groq, and LM Studio.
- **Natural Language Understanding**: Leverages configurable LLM providers to understand and generate human-like responses.
- **PDF Summary Generation**: Generates PDF summaries of voice interactions, including a question header, AI-generated response, and an accompanying logo.
- **Caching Mechanism**: Implements a SQLite-based caching system to store and retrieve past queries and responses, reducing API calls and improving response times.
- **Voice Recognition**: Integrates with speech recognition libraries to support voice input.
- **Text-to-Speech**: Converts text responses into speech, providing an interactive voice-based user experience.

## Setup

### Prerequisites

- Python 3.9+
- Pipenv or virtualenv

![divider][divider]

### Installation

#### 1. Clone the repository

```bash
git clone https://github.com/sebastienrousseau/akande
cd akande
```

#### 2. Install dependencies

```bash
pipenv install  # If using pipenv
# or
python -m venv venv
source venv/bin/activate  # On Windows use `venv\Scripts\activate`
pip install -r requirements.txt
```

#### 3. Set up environment variables

Copy `.env.example` to `.env` and configure your LLM provider:

```bash
cp .env.example .env
# Edit .env with your provider choice and API key
LLM_PROVIDER=openai          # or anthropic, google, ollama, etc.
OPENAI_API_KEY=sk-your-key   # Set the key for your chosen provider
```

See `.env.example` for the full list of supported providers and their
configuration options.

#### 4. Running Àkàndé

```bash
pipenv run python -m akande  # If using pipenv
# or
python -m akande
```

![divider][divider]

## Usage

After starting Àkàndé, simply follow the voice prompts to ask questions.
Àkàndé will respond verbally and generate a PDF summary for each interaction
in the specified output directory.

![divider][divider]

## Contributing

Pull requests are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

![divider][divider]

## License

This project is licensed under the Apache Software License - see the [LICENSE](LICENSE) file for details.

![divider][divider]

[divider]: https://kura.pro/common/images/elements/divider.svg "Divider"
[banner]: https://kura.pro/akande/images/titles/title-akande.webp "Banner for Àkàndé - Voice Assistant"
