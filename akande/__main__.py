# Copyright (C) 2024 Sebastien Rousseau.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
import asyncio
import logging

from .akande import Akande
from .config import LLM_PROVIDER, OPENAI_API_KEY
from .logger import basic_config
from .providers import get_provider
from .services import OpenAIImpl
from .utils import (
    get_output_directory,
    get_output_filename,
    validate_api_key,
)


async def main():
    """
    Main function to initialize and run the Akande voice assistant.
    """
    provider_name = LLM_PROVIDER or "openai"

    # For OpenAI provider, validate the API key format
    if provider_name == "openai" and not validate_api_key(
        OPENAI_API_KEY
    ):
        logging.error(
            "Invalid or missing OPENAI_API_KEY",
            extra={"event": "Config:ValidationFailed"},
        )
        return

    try:
        provider = get_provider(provider_name)
    except (ValueError, ImportError) as e:
        logging.error(
            "Provider initialization failed",
            extra={
                "event": "Provider:InitFailed",
                "extra_data": {
                    "provider": provider_name,
                    "error": type(e).__name__,
                },
            },
        )
        return

    # Use the resolved provider. For backward compatibility,
    # wrap it in a lightweight OpenAIImpl when OpenAI is
    # selected; otherwise use the provider directly.
    if provider_name == "openai":
        openai_service = OpenAIImpl()
    else:
        openai_service = provider
    akande = Akande(openai_service=openai_service)
    try:
        await akande.run_interaction()
    except KeyboardInterrupt:
        logging.info(
            "Keyboard interrupt detected, exiting",
            extra={"event": "Session:Ended"},
        )
        await akande.stop_server()


def run():
    """Synchronous entry point for console_scripts."""
    directory_path = get_output_directory()
    filename = get_output_filename(".log")
    file_path = directory_path / filename

    log_level = logging.INFO
    log_format = "%(asctime)s - %(levelname)s - %(message)s"
    basic_config(
        filename=str(file_path),
        level=log_level,
        log_format=log_format,
    )

    asyncio.run(main())


if __name__ == "__main__":
    run()
