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
import sys

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


def _build_akande() -> Akande:
    """Validate config and return an Akande instance."""
    provider_name = LLM_PROVIDER or "openai"

    if provider_name == "openai" and not validate_api_key(
        OPENAI_API_KEY
    ):
        logging.error(
            "Invalid or missing OPENAI_API_KEY",
            extra={"event": "Config:ValidationFailed"},
        )
        print(
            "Error: Invalid or missing OPENAI_API_KEY. "
            "Check your .env file."
        )
        sys.exit(1)

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
        print(
            f"Error: Could not load provider "
            f"'{provider_name}': {e}"
        )
        sys.exit(1)

    if provider_name == "openai":
        openai_service = OpenAIImpl()
    else:
        openai_service = provider
    return Akande(openai_service=openai_service)


async def main():
    """Run the classic CLI interaction loop."""
    akande = _build_akande()
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

    # Use --classic flag to fall back to the plain CLI
    if "--classic" in sys.argv:
        asyncio.run(main())
        return

    # In TUI mode, reconfigure logging to file-only so log lines
    # don't corrupt Textual's alternate screen buffer.
    basic_config(
        filename=str(file_path),
        level=log_level,
        log_format=log_format,
        console=False,
    )
    # Suppress CherryPy's own console logging in TUI mode
    logging.getLogger("cherrypy").setLevel(logging.WARNING)
    logging.getLogger("cherrypy.error").setLevel(logging.WARNING)
    logging.getLogger("cherrypy.access").setLevel(logging.WARNING)

    from .tui import AkandeApp

    akande = _build_akande()
    app = AkandeApp(akande)
    app.run()


if __name__ == "__main__":
    run()
