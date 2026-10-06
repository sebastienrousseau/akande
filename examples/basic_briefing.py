# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Basic text briefing example using the Àkàndé pipeline."""

import os

from akande.pipeline import run_pipeline


def main() -> None:
    # Select default provider if not set in environment
    if "LLM_PROVIDER" not in os.environ:
        os.environ["LLM_PROVIDER"] = "ollama"

    prompt = (
        "Provide a concise morning executive briefing on market trends."
    )
    print(f"Executing briefing request: '{prompt}'")

    result = run_pipeline(prompt)

    print("\n--- Briefing Summary ---")
    print(result.summary)
    print("\n--- Full Response ---")
    print(result.response)


if __name__ == "__main__":
    main()
