# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Voice interaction example using Àkàndé STT, assistant, and TTS backends."""

import asyncio
import os

from akande.akande import Akande
from akande.providers.registry import get_provider
from akande.stt import get_stt_backend
from akande.tts import get_tts_backend


async def main() -> None:
    # Configure backends
    stt_backend = get_stt_backend()
    tts_backend = get_tts_backend()

    print(f"STT Backend: {type(stt_backend).__name__}")
    print(f"TTS Backend: {type(tts_backend).__name__}")

    # Simulated or captured voice query
    query_text = "What is our scheduled executive summary today?"
    print(f"\nUser query: '{query_text}'")

    if "LLM_PROVIDER" not in os.environ:
        os.environ["LLM_PROVIDER"] = "ollama"

    provider = get_provider()
    assistant = Akande(openai_service=provider)

    response = await assistant.generate_response(query_text)
    print(f"\nResponse: {response}")

    # Synthesise audio response
    print("\nSynthesising speech response...")
    synthesis = tts_backend.synthesise(response)
    print(
        f"Synthesised {len(synthesis.audio)} bytes of audio "
        f"({synthesis.fmt})."
    )


if __name__ == "__main__":
    asyncio.run(main())
