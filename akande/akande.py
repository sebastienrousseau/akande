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
from .config import LLM_PROVIDER, OPENAI_DEFAULT_MODEL
from .exceptions import LLMError
from .providers.base import LLMProvider
from .services import SYSTEM_PROMPT, OpenAIService
from .utils import (
    generate_pdf,
    generate_csv,
    get_output_directory,
    get_output_filename,
    strip_markdown,
)

from concurrent.futures import ThreadPoolExecutor
from functools import partial
from typing import Optional, Union
import asyncio
import hashlib
import logging
import openai
import time
import threading
import uuid
import speech_recognition as sr
from gtts import gTTS
from pydub import AudioSegment
from pydub.playback import play as pydub_play

try:
    import pyttsx4

    _PYTTSX4_AVAILABLE = True
except ImportError:
    _PYTTSX4_AVAILABLE = False


def _friendly_llm_error(exc: Exception) -> str:
    """Return a user-facing message for common LLM errors."""
    if isinstance(exc, openai.AuthenticationError):
        return (
            "Your API key is invalid or has been revoked. "
            "Please check the key in your .env file."
        )
    if isinstance(exc, openai.RateLimitError):
        msg = str(exc)
        if "insufficient_quota" in msg:
            return (
                "Your API account has run out of credits. "
                "Please check your plan and billing details "
                "at https://platform.openai.com/account/billing"
            )
        return (
            "The API rate limit has been reached. "
            "Please wait a moment and try again."
        )
    if isinstance(exc, openai.APIConnectionError):
        return (
            "Could not connect to the LLM provider. "
            "Please check your internet connection."
        )
    if isinstance(exc, openai.APITimeoutError):
        return (
            "The request to the LLM provider timed out. "
            "Please try again."
        )
    return (
        "An error occurred while contacting the "
        f"LLM provider: {type(exc).__name__}"
    )


MAX_THREAD_WORKERS = 4
CACHE_DB_NAME = "akande_cache.db"


# Define ANSI escape codes for colors
class Colors:
    RESET = "\033[0m"
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

    def __init__(
        self,
        openai_service: Union[OpenAIService, LLMProvider],
        metrics=None,
    ):
        self.server = None
        self.server_thread: Optional[threading.Thread] = None
        self._server_running = threading.Event()

        # Cancellation support
        self._cancel_event = threading.Event()

        # Optional telemetry
        self.metrics = metrics

        # Use a stable cache DB path (date-based dir, fixed name)
        directory_path = get_output_directory()
        cache_path = directory_path / CACHE_DB_NAME

        self.openai_service = openai_service
        self.recognizer = sr.Recognizer()
        self.cache = SQLiteCache(str(cache_path))
        self.executor = ThreadPoolExecutor(
            max_workers=MAX_THREAD_WORKERS
        )

        logging.info(
            "TTS engine initialized (gTTS)",
            extra={"event": "TTS:Initialized"},
        )

    @property
    def server_running(self):
        return self._server_running.is_set()

    @server_running.setter
    def server_running(self, value: bool):
        if value:
            self._server_running.set()
        else:
            self._server_running.clear()

    def cancel_pending(self) -> None:
        """Signal any in-flight request to abort."""
        self._cancel_event.set()

    def reset_cancel(self) -> None:
        """Clear the cancellation flag."""
        self._cancel_event.clear()

    def hash_prompt(self, prompt: str) -> str:
        """Hash the prompt for caching."""
        return hashlib.sha256(
            prompt.encode("utf-8")
        ).hexdigest()

    async def speak(self, text: str) -> None:
        """
        Speak the given text using gTTS in an async manner.

        Generates an MP3 via Google Text-to-Speech, saves it to
        the output directory, and plays it back using pydub.
        Falls back to pyttsx4 for offline TTS if gTTS fails.
        """
        if self._cancel_event.is_set():
            raise LLMError("Request was cancelled")

        def tts_engine_run(text: str):
            start = time.time()
            directory_path = get_output_directory()
            mp3_filename = get_output_filename(".mp3")
            mp3_path = directory_path / mp3_filename
            try:
                tts = gTTS(text=text, lang="en", tld="co.uk")
                tts.save(str(mp3_path))

                audio = AudioSegment.from_mp3(str(mp3_path))
                pydub_play(audio)

                latency = (time.time() - start) * 1000
                if self.metrics:
                    self.metrics.record("tts", latency)
                logging.info(
                    "TTS synthesis completed",
                    extra={
                        "event": "Speech:SynthesisCompleted",
                        "extra_data": {
                            "audio_file": str(mp3_path),
                            "text_length": len(text),
                            "latency_ms": round(latency, 2),
                        },
                    },
                )
            except Exception as e:
                logging.warning(
                    f"gTTS failed: {type(e).__name__}, "
                    f"trying pyttsx4 fallback",
                    extra={
                        "event": "Speech:gTTSFailed",
                    },
                )
                if _PYTTSX4_AVAILABLE:
                    try:
                        engine = pyttsx4.init()
                        engine.say(text)
                        engine.runAndWait()
                        latency = (
                            (time.time() - start) * 1000
                        )
                        if self.metrics:
                            self.metrics.record(
                                "tts", latency
                            )
                        logging.info(
                            "pyttsx4 fallback succeeded",
                            extra={
                                "event": (
                                    "Speech:pyttsx4Completed"
                                ),
                            },
                        )
                        return
                    except Exception as e2:
                        logging.error(
                            f"pyttsx4 fallback failed: "
                            f"{type(e2).__name__}",
                            exc_info=True,
                            extra={
                                "event": (
                                    "Speech:pyttsx4Failed"
                                ),
                            },
                        )
                else:
                    logging.error(
                        "No offline TTS available "
                        "(pyttsx4 not installed)",
                        extra={
                            "event": (
                                "Speech:SynthesisFailed"
                            ),
                        },
                    )

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            self.executor, partial(tts_engine_run, text)
        )

    async def listen(self, speak_on_error: bool = True) -> str:
        """Listen for user input and return the recognized text.

        Args:
            speak_on_error: If True, speak an error message when
                recognition fails.  Set to False in TUI mode to
                avoid audio playback that corrupts the display.
        """

        def _listen_sync():
            try:
                start = time.time()
                with sr.Microphone() as source:
                    logging.info(
                        "Listening for user input",
                        extra={
                            "event": "Speech:RecognitionStarted",
                        },
                    )
                    audio = self.recognizer.listen(source)
                text = self.recognizer.recognize_google(audio)
                latency = (time.time() - start) * 1000
                if self.metrics:
                    self.metrics.record("stt", latency)
                logging.info(
                    "Speech recognized",
                    extra={
                        "event": "Speech:RecognitionCompleted",
                        "extra_data": {
                            "success": True,
                            "transcript_length": len(text),
                            "latency_ms": round(latency, 2),
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
            except AttributeError:
                logging.error(
                    "PyAudio is not installed. "
                    "Install it with: pip install pyaudio",
                    extra={
                        "event": "Speech:DependencyMissing",
                        "extra_data": {
                            "dependency": "pyaudio",
                        },
                    },
                )
                return ""
            except OSError as e:
                logging.error(
                    f"Microphone error: {e}",
                    exc_info=True,
                    extra={
                        "event": "Speech:MicrophoneError",
                        "extra_data": {
                            "error_type": type(e).__name__,
                        },
                    },
                )
                return ""

        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            self.executor, _listen_sync
        )
        if not result and speak_on_error:
            await self.speak(
                "I'm sorry, I couldn't understand what you said."
            )
        return result

    def _print_banner(self) -> None:
        """Print the application banner with provider info."""
        provider = LLM_PROVIDER or "openai"
        model = OPENAI_DEFAULT_MODEL or "default"
        print(CLEAR_SCREEN, end="", flush=True)
        print(
            f"{Colors.CYAN_BACKGROUND}"
            f"  Àkàndé Voice Assistant  "
            f"{Colors.RESET}"
        )
        print(
            f"  Provider: {provider}  |  "
            f"Model: {model}"
        )
        print()

    def _print_menu(self) -> None:
        """Print the menu options."""
        options = [
            ("1", "Voice input", Colors.BLUE_BACKGROUND),
            ("2", "Text question", Colors.GREEN_BACKGROUND),
            ("3", "Web server", Colors.ORANGE_BACKGROUND),
            ("4", "Quit", Colors.RED_BACKGROUND),
        ]
        for key, label, color in options:
            print(
                f"  {color} {key} {Colors.RESET} {label}"
            )
        print()

    async def _generate_files(
        self, question: str, response: str, clean: str
    ) -> None:
        """Generate PDF and CSV files and display their paths."""
        loop = asyncio.get_running_loop()
        pdf_future = loop.run_in_executor(
            self.executor,
            generate_pdf,
            question,
            response,
        )
        csv_future = loop.run_in_executor(
            self.executor,
            generate_csv,
            question,
            clean,
        )
        pdf_path = await pdf_future
        csv_path = await csv_future
        print("  Generated files:")
        if pdf_path:
            print(f"    PDF: {pdf_path}")
        if csv_path:
            print(f"    CSV: {csv_path}")
        print()

    async def _handle_response(
        self, question: str, correlation_id: str
    ) -> None:
        """Query the LLM, display response, speak it, and
        generate output files."""
        try:
            response = await self.generate_response(
                question,
                correlation_id=correlation_id,
            )
        except LLMError as e:
            print(f"\nError: {e.user_message}\n")
            return
        if not response:
            print("Sorry, no response was generated.")
            return

        clean = strip_markdown(response)
        print(f"\n{clean}\n")
        await self.speak(clean)
        await self._generate_files(question, response, clean)

    async def run_interaction(self) -> None:
        """Main interaction loop of the voice assistant."""
        while True:
            self._print_banner()
            self._print_menu()

            choice = input("Select [1-4]: ").strip()

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
                print(
                    "  Server running at "
                    "http://127.0.0.1:8080"
                )
                print(
                    "  Open the URL in your browser."
                )
                input("\n  Press Enter to continue...")
            elif choice == "2":
                question = input(
                    "Your question: "
                ).strip()
                if question:
                    print("Processing...")
                    await self._handle_response(
                        question, correlation_id
                    )
                else:
                    print("No question provided.")
                input("Press Enter to continue...")
            elif choice == "1":
                print("Listening...")
                prompt = (await self.listen()).lower()
                if prompt == "stop":
                    print("\nGoodbye!")
                    await self.stop_server()
                    break
                elif prompt:
                    print(f'Heard: "{prompt}"')
                    print("Processing...")
                    await self._handle_response(
                        prompt, correlation_id
                    )
                else:
                    print("No voice command detected.")
                input("Press Enter to continue...")
            else:
                print("Invalid choice.")
                input("Press Enter to continue...")

    async def run_server(self) -> None:
        """Run the CherryPy server in a separate thread."""
        if self.server_running:
            logging.info(
                "Server is already running",
                extra={"event": "Server:AlreadyRunning"},
            )
            return

        def start_server():
            from .server.server import (
                AkandeServer,
                MAX_AUDIO_SIZE,
            )

            cherrypy.config.update(
                {
                    "server.socket_host": "127.0.0.1",
                    "server.socket_port": 8080,
                    "server.thread_pool": 30,
                    "server.max_request_body_size": (
                        MAX_AUDIO_SIZE
                    ),
                    "request.show_tracebacks": False,
                    "request.show_mismatched_params": False,
                    "log.screen": False,
                }
            )
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
        """Stop the CherryPy server and release resources."""
        self.server_running = False
        cherrypy.engine.exit()
        self.cache.close()
        self.executor.shutdown(wait=False)
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

        Raises:
            LLMError: When the LLM call fails or the request
                is cancelled.
        """
        if self._cancel_event.is_set():
            raise LLMError("Request was cancelled")

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
                start = time.time()
                response = (
                    await self.openai_service.generate_response(
                        prompt,
                        SYSTEM_PROMPT,
                        OPENAI_DEFAULT_MODEL or "gpt-4o-mini",
                        {},
                    )
                )
                latency = (time.time() - start) * 1000
                if self.metrics:
                    self.metrics.record("llm", latency)
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
            except LLMError:
                raise
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
                raise LLMError(
                    _friendly_llm_error(e), original=e
                )
