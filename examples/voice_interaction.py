# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Voice interaction example using Àkàndé STT, pipeline, and TTS backends."""

import os

from akande.pipeline import run_pipeline
from akande.stt import get_stt_backend
from akande.tts import get_tts_backend


def main() -> None:
    # Configure backends
    stt_backend = get_stt_backend()
    tts_backend = get_tts_backend()

    print(f"STT Backend: {type(stt_backend).__name__}")
    print(f"TTS Backend: {type(tts_backend).__name__}")

    # Simulated or captured voice query
    query_text = "What is our scheduled executive summary today?"
    print(f"\nUser query: '{query_text}'")

    # Run orchestration pipeline
    if "LLM_PROVIDER" not in os.environ:
        os.environ["LLM_PROVIDER"] = "ollama"

    result = run_pipeline(query_text)
    print(f"\nResponse: {result.response}")

    # Synthesize audio response
    print("\nSynthesizing speech response...")
    synthesis = tts_backend.synthesize(result.response)
    print(
        f"Synthesized {len(synthesis.audio_bytes)} bytes of audio "
        f"({synthesis.mime_type})."
    )


if __name__ == "__main__":
    main()
