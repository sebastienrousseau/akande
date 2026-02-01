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
import cherrypy
from .cache import SQLiteCache
from .config import OPENAI_DEFAULT_MODEL
from .services import SYSTEM_PROMPT, OpenAIService
from .utils import (
    generate_pdf,
    generate_csv,
    get_output_directory,
    get_output_filename,
)

from concurrent.futures import ThreadPoolExecutor
from functools import partial
import asyncio
import hashlib
import logging
import pyttsx4
import threading
import uuid
import speech_recognition as sr

MAX_THREAD_WORKERS = 4
TTS_RATE = 161
CACHE_DB_NAME = "akande_cache.db"


# Define ANSI escape codes for colors
class Colors:
    RESET = "\033[0m"
    HEADER = "\033[95m"
    RED_BACKGROUND = "\033[48;2;179;0;15m"
    CYAN_BACKGROUND = "\033[48;2;65;175;220m"
    GREEN_BACKGROUND = "\033[48;2;0;103;0m"
    BLUE_BACKGROUND = "\033[48;2;0;78;203m"
    ORANGE_BACKGROUND = "\033[48;2;150;61;0m"


# ANSI escape sequence to clear terminal (replaces subprocess call)
CLEAR_SCREEN = "\033[2J\033[H"


class Akande:
    """
    The Akande voice assistant.

    This class represents the voice assistant capable of understanding
    and responding to user queries. It integrates speech recognition
    and synthesis, leveraging configurable LLM providers for
    generating responses.
    """

    def __init__(self, openai_service: OpenAIService):
        self.server = None
        self.server_thread = None
        self.server_running = False

        # Use a stable cache DB path (date-based dir, fixed name)
        directory_path = get_output_directory()
        cache_path = directory_path / CACHE_DB_NAME

        self.openai_service = openai_service
        self.recognizer = sr.Recognizer()
        self.cache = SQLiteCache(cache_path)
        self.executor = ThreadPoolExecutor(
            max_workers=MAX_THREAD_WORKERS
        )

        # Initialize TTS engine once
        try:
            self._tts_engine = pyttsx4.init()
            self._tts_engine.setProperty("rate", TTS_RATE)
            logging.info(
                "TTS engine initialized",
                extra={"event": "TTS:Initialized"},
            )
        except Exception as e:
            logging.error(
                f"Failed to init TTS engine: "
                f"{type(e).__name__}",
                exc_info=True,
                extra={"event": "TTS:InitFailed"},
            )
            self._tts_engine = None

    def hash_prompt(self, prompt: str) -> str:
        """Hash the prompt for caching."""
        return hashlib.sha256(
            prompt.encode("utf-8")
        ).hexdigest()

    async def speak(self, text: str) -> None:
        """
        Speak the given text using pyttsx4 in an async manner.

        Uses a ThreadPoolExecutor to run blocking TTS operations
        in a separate thread.
        """

        def tts_engine_run(text: str):
            directory_path = get_output_directory()
            filename = get_output_filename(".wav")
            file_path = directory_path / filename
            try:
                if self._tts_engine is not None:
                    self._tts_engine.save_to_file(
                        text, str(file_path)
                    )
                    self._tts_engine.runAndWait()
                    logging.info(
                        "TTS synthesis completed",
                        extra={
                            "event": "Speech:SynthesisCompleted",
                            "extra_data": {
                                "wav_file": str(file_path),
                                "text_length": len(text),
                            },
                        },
                    )
                else:
                    logging.warning(
                        "TTS engine not available",
                        extra={
                            "event": "TTS:Unavailable",
                        },
                    )
            except Exception as e:
                logging.error(
                    f"Error during speech synthesis: "
                    f"{type(e).__name__}",
                    exc_info=True,
                    extra={"event": "Speech:SynthesisFailed"},
                )

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            self.executor, partial(tts_engine_run, text)
        )

    async def listen(self) -> str:
        """Listen for user input and return the recognized text."""

        def _listen_sync():
            try:
                with sr.Microphone() as source:
                    logging.info(
                        "Listening for user input",
                        extra={
                            "event": "Speech:RecognitionStarted",
                        },
                    )
                    audio = self.recognizer.listen(source)
                text = self.recognizer.recognize_google(audio)
                logging.info(
                    "Speech recognized",
                    extra={
                        "event": "Speech:RecognitionCompleted",
                        "extra_data": {
                            "success": True,
                            "transcript_length": len(text),
                        },
                    },
                )
                return text
            except sr.UnknownValueError:
                logging.warning(
                    "Speech could not be understood",
                    extra={
                        "event": "Speech:RecognitionCompleted",
                        "extra_data": {
                            "success": False,
                            "error_type": "UnknownValueError",
                        },
                    },
                )
                return ""
            except sr.RequestError as e:
                logging.error(
                    f"Speech recognition service error: "
                    f"{type(e).__name__}",
                    exc_info=True,
                    extra={
                        "event": "Speech:RecognitionCompleted",
                        "extra_data": {
                            "success": False,
                            "error_type": "RequestError",
                        },
                    },
                )
                return ""

        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            self.executor, _listen_sync
        )
        if not result:
            await self.speak(
                "I'm sorry, I couldn't understand what you said."
            )
        return result

    async def run_interaction(self) -> None:
        """Main interaction loop of the voice assistant."""
        while True:
            # Clear screen using ANSI escape (no subprocess)
            print(CLEAR_SCREEN, end="", flush=True)
            banner_text = "Àkàndé Voice Assistant"
            banner_width = len(banner_text) + 4
            print(f"{Colors.RESET}{' ' * banner_width}")
            print("  " + banner_text + "  ")
            print(" " * banner_width + Colors.RESET)

            options = [
                ("1. Use voice", Colors.BLUE_BACKGROUND),
                ("2. Ask a question", Colors.GREEN_BACKGROUND),
                ("3. Start server", Colors.ORANGE_BACKGROUND),
                ("4. Stop", Colors.RED_BACKGROUND),
            ]

            for option_text, color in options:
                print(
                    f"{color}{' ' * banner_width}{Colors.RESET}"
                )
                print(
                    f"{color}{option_text:<{banner_width}}"
                    f"{Colors.RESET}"
                )
                print(
                    f"{color}{' ' * banner_width}{Colors.RESET}"
                )

            choice = input(
                "\nPlease select an option: "
            ).strip()

            # Generate correlation ID for this interaction
            correlation_id = str(uuid.uuid4())
            logging.info(
                f"Menu option selected: {choice}",
                extra={
                    "event": "Interaction:MenuSelected",
                    "correlation_id": correlation_id,
                    "extra_data": {"choice": choice},
                },
            )

            if choice == "4":
                print("\nGoodbye!")
                await self.stop_server()
                break
            elif choice == "3":
                await self.run_server()
            elif choice == "2":
                question = input(
                    "Please enter your question: "
                ).strip()
                if question:
                    print("Processing question...")
                    response = await self.generate_response(
                        question,
                        correlation_id=correlation_id,
                    )
                    await self.speak(response)
                    # Offload file generation to background thread
                    loop = asyncio.get_running_loop()
                    loop.run_in_executor(
                        self.executor,
                        generate_pdf,
                        question,
                        response,
                    )
                    loop.run_in_executor(
                        self.executor,
                        generate_csv,
                        question,
                        response,
                    )
                else:
                    print("No question provided.")
            elif choice == "1":
                print("Listening...")
                prompt = (await self.listen()).lower()
                if prompt == "stop":
                    print("\nGoodbye!")
                    await self.stop_server()
                    break
                elif prompt:
                    print("Processing voice command...")
                    response = await self.generate_response(
                        prompt,
                        correlation_id=correlation_id,
                    )
                    await self.speak(response)
                    # Offload file generation to background thread
                    loop = asyncio.get_running_loop()
                    loop.run_in_executor(
                        self.executor,
                        generate_pdf,
                        prompt,
                        response,
                    )
                    loop.run_in_executor(
                        self.executor,
                        generate_csv,
                        prompt,
                        response,
                    )
                else:
                    print("No voice command detected.")
            else:
                print(
                    "Invalid choice. Please select a valid option."
                )

    async def run_server(self) -> None:
        """Run the CherryPy server in a separate thread."""
        if self.server_running:
            logging.info(
                "Server is already running",
                extra={"event": "Server:AlreadyRunning"},
            )
            return

        def start_server():
            from .server.server import AkandeServer

            cherrypy.quickstart(AkandeServer())

        self.server_running = True
        self.server_thread = threading.Thread(
            target=start_server, daemon=True
        )
        self.server_thread.start()
        logging.info(
            "CherryPy server started",
            extra={
                "event": "Server:Started",
                "extra_data": {"port": 8080},
            },
        )

    async def stop_server(self) -> None:
        """Stop the CherryPy server."""
        self.server_running = False
        cherrypy.engine.exit()
        logging.info(
            "CherryPy server stopped",
            extra={"event": "Server:Stopped"},
        )

    async def generate_response(
        self,
        prompt: str,
        correlation_id: str = "",
    ) -> str:
        """
        Generate a response using the LLM provider or cache.

        Args:
            prompt: The prompt for generating the response.
            correlation_id: Optional correlation ID for tracing.

        Returns:
            The generated response.
        """
        prompt_hash = self.hash_prompt(prompt)
        cached_response = self.cache.get(prompt_hash)
        if cached_response:
            logging.info(
                "Using cached response",
                extra={
                    "event": "Response:CacheHit",
                    "correlation_id": correlation_id,
                    "extra_data": {
                        "prompt_hash": prompt_hash[:12],
                    },
                },
            )
            return cached_response
        else:
            logging.info(
                "Cache miss, calling LLM provider",
                extra={
                    "event": "Response:CacheMiss",
                    "correlation_id": correlation_id,
                    "extra_data": {
                        "prompt_hash": prompt_hash[:12],
                    },
                },
            )
            try:
                response = (
                    await self.openai_service.generate_response(
                        prompt,
                        SYSTEM_PROMPT,
                        OPENAI_DEFAULT_MODEL,
                        {},
                    )
                )
                if not hasattr(response, "choices"):
                    logging.error(
                        "LLM returned unexpected response type",
                        extra={
                            "event": "LLM:UnexpectedResponse",
                            "correlation_id": correlation_id,
                            "extra_data": {
                                "response_type": type(
                                    response
                                ).__name__,
                            },
                        },
                    )
                    return ""
                text_response = (
                    response.choices[0].message.content.strip()
                    if response.choices
                    else ""
                )
                self.cache.set(prompt_hash, text_response)
                return text_response
            except Exception as e:
                logging.error(
                    f"LLM API error: "
                    f"{type(e).__name__}: {e}",
                    exc_info=True,
                    extra={
                        "event": "LLM:Error",
                        "correlation_id": correlation_id,
                    },
                )
                return ""
