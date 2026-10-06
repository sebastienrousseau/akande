# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Basic text briefing example using the Àkàndé library."""

import asyncio
import os

from akande.akande import Akande
from akande.providers.registry import get_provider


async def main() -> None:
    # Select default provider if not set in environment
    if "LLM_PROVIDER" not in os.environ:
        os.environ["LLM_PROVIDER"] = "ollama"

    provider = get_provider()
    assistant = Akande(openai_service=provider)

    prompt = (
        "Provide a concise morning executive briefing on market trends."
    )
    print(f"Executing briefing request: '{prompt}'")

    response = await assistant.generate_response(prompt)

    print("\n--- Briefing Response ---")
    print(response)


if __name__ == "__main__":
    asyncio.run(main())
