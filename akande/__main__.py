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
from .akande import Akande
from .config import OPENAI_API_KEY
from .logger import basic_config
from .services import OpenAIImpl
from .utils import validate_api_key
import asyncio
from datetime import datetime
import logging
from pathlib import Path


async def main():
    """
    Main function to initialize and run the Akande voice assistant.

    This function checks for the presence of the OPENAI_API_KEY environment
    variable. If the variable is missing or invalid, an error message is logged
    and the function returns. Otherwise, it creates an instance of the
    OpenAIImpl class and the Akande class, and then runs the interaction loop
    of the Akande voice assistant.
    """
    # Validate the OPENAI_API_KEY
    if not validate_api_key(OPENAI_API_KEY):
        logging.error(
            "Invalid or missing OPENAI_API_KEY in environment variables."
        )
        return

    openai_service = OpenAIImpl()
    akande = Akande(openai_service=openai_service)
    await akande.run_interaction()


if __name__ == "__main__":
    # Create a directory path with the current date
    date_str = datetime.now().strftime("%Y-%m-%d")
    directory_path = Path(date_str)
    # Ensure the directory exists
    directory_path.mkdir(parents=True, exist_ok=True)

    # Create the WAV filename with timestamp
    filename = datetime.now().strftime("%Y-%m-%d-%H-%M-Akande") + ".log"
    file_path = directory_path / filename

    # Setup logging configuration
    log_file = file_path
    log_level = logging.DEBUG
    log_format = "%(asctime)s - %(levelname)s - %(message)s"
    basic_config(
        filename=log_file, level=log_level, log_format=log_format
    )

    # Run the main async function
    asyncio.run(main())
