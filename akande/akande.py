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
from .services import OpenAIService

from .utils import generate_pdf, generate_csv
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from functools import partial
from pathlib import Path
import asyncio
import hashlib
import logging
import pyttsx4
import threading
import speech_recognition as sr
import os


# Define ANSI escape codes for colors
class Colors:
    RESET = "\033[0m"
    HEADER = "\033[95m"
    RED_BACKGROUND = "\033[48;2;179;0;15m"
    CYAN_BACKGROUND = "\033[48;2;65;175;220m"
    GREEN_BACKGROUND = "\033[48;2;0;103;0m"
    BLUE_BACKGROUND = "\033[48;2;0;78;203m"
    ORANGE_BACKGROUND = "\033[48;2;150;61;0m"


class Akande:
    """
    The Akande voice assistant.

    This class represents the voice assistant capable of understanding and
    responding to user queries. It integrates speech recognition and synthesis,
    leveraging OpenAI's GPT models for generating responses.
    """

    def __init__(self, openai_service: OpenAIService):
        """
        Initialize the voice assistant with necessary services and settings.

        Args:
            openai_service (OpenAIService): The OpenAI service for
            generating responses.
        """
        # Initialize the CherryPy server attribute
        self.server = None
        self.server_thread = None
        self.server_running = False

        # Create a directory path with the current date
        date_str = datetime.now().strftime("%Y-%m-%d")
        directory_path = Path(date_str)
        # Ensure the directory exists
        directory_path.mkdir(parents=True, exist_ok=True)

        # Create the WAV filename with timestamp
        filename = (
            datetime.now().strftime("%Y-%m-%d-%H-%M-Akande_Cache")
            + ".db"
        )
        file_path = directory_path / filename

        self.openai_service = openai_service
        self.recognizer = sr.Recognizer()
        self.cache = SQLiteCache(file_path)
        self.executor = ThreadPoolExecutor(max_workers=4)

    def hash_prompt(self, prompt: str) -> str:
        """
        Hash the prompt for caching.

        Args:
            prompt (str): The prompt to be hashed.

        Returns:
            str: The hashed prompt.

        """
        return hashlib.sha256(prompt.encode("utf-8")).hexdigest()

    async def speak(self, text: str) -> None:
        """
        Speak the given text using pyttsx3 in an asynchronous manner.

        This method utilizes a ThreadPoolExecutor to run pyttsx3's blocking
        operations in a separate thread, allowing the asyncio event loop to
        remain responsive.

        Args:
            text (str): The text to be spoken.

        Returns:
            None: This function does not return any values.
        """

        def tts_engine_run(text: str):
            """
            Generates a WAV file from the given text using pyttsx3.

            This function initializes a text-to-speech engine, sets its
            properties, and saves the spoken text as a WAV file in a directory
            named with the current date (%Y-%m-%d).

            The filename is timestamped to ensure uniqueness.

            Parameters:
            text (str): The text to be converted to speech.

            Raises:
            Exception: If an error occurs during speech synthesis, it is
            raised as an exception.
            """
            # Create a directory path with the current date
            date_str = datetime.now().strftime("%Y-%m-%d")
            directory_path = Path(date_str)
            # Ensure the directory exists
            directory_path.mkdir(parents=True, exist_ok=True)

            # Create the WAV filename with timestamp
            filename = (
                datetime.now().strftime("%Y-%m-%d-%H-%M-Akande")
                + ".wav"
            )
            file_path = directory_path / filename
            try:
                engine = pyttsx4.init()
                engine.setProperty("rate", 161)
                engine.say(text)
                engine.save_to_file(text, str(file_path))
                engine.runAndWait()
                logging.info(f"WAV file generated: {file_path}")
            except Exception as e:
                logging.error(
                    f"Error using pyttsx3 for speech synthesis: {e}"
                )

        await asyncio.get_event_loop().run_in_executor(
            self.executor, partial(tts_engine_run, text)
        )

    async def listen(self) -> str:
        """Listen for user input and return the recognized text."""
        try:
            with sr.Microphone() as source:
                logging.info("Listening for user input...")
                audio = self.recognizer.listen(source)
            return self.recognizer.recognize_google(audio)
        except sr.UnknownValueError:
            await self.speak(
                "I'm sorry, I couldn't understand what you said."
            )
            return ""
        except sr.RequestError as e:
            logging.error(f"Speech recognition service error {e}")
            await self.speak(
                """
                I'm sorry, I encountered an error with the speech recognition
                service.
                """
            )
            return ""

    async def run_interaction(self) -> None:
        """Main interaction loop of the voice assistant."""
        while True:
            os.system(
                "clear"
            )  # Clear the console for better visualization
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
                print(f"{color}{' ' * banner_width}{Colors.RESET}")
                print(
                    f"{color}{option_text:<{banner_width}}{Colors.RESET}"
                )
                print(f"{color}{' ' * banner_width}{Colors.RESET}")

            choice = input("\nPlease select an option: ").strip()

            if choice == "4":
                print("\nGoodbye!")
                await self.stop_server()
                break
            elif choice == "3":
                await self.run_server()
            elif choice == "2":
                question = input("Please enter your question: ").strip()
                if question:
                    print("Processing question...")
                    response = await self.generate_response(question)
                    await self.speak(response)
                    await generate_pdf(question, response)
                    await generate_csv(question, response)
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
                    response = await self.generate_response(prompt)
                    await self.speak(response)
                    await generate_pdf(prompt, response)
                    await generate_csv(prompt, response)
                else:
                    print("No voice command detected.")
            else:
                print("Invalid choice. Please select a valid option.")

    async def run_server(self) -> None:
        """Run the CherryPy server in a separate thread."""

        # Define a function to start the server
        def start_server():
            from .server.server import AkandeServer

            cherrypy.quickstart(AkandeServer())

            # Set server_running flag to True
            self.server_running = True

        # Start the server in a separate thread
        server_thread = threading.Thread(target=start_server)
        server_thread.start()
        logging.info("CherryPy server started.")

    async def stop_server(self) -> None:
        """Stop the CherryPy server."""
        self.server_running = False
        cherrypy.engine.exit()
        logging.info("CherryPy server stopped.")

    async def generate_response(self, prompt: str) -> str:
        """
        Generate a response using the OpenAI service or cache.

        Args:
            prompt (str): The prompt for generating the response.

        Returns:
            str: The generated response.

        """
        prompt_hash = self.hash_prompt(prompt)
        cached_response = self.cache.get(prompt_hash)
        if cached_response:
            logging.info(f"Cache hit for prompt: {prompt}")
            return cached_response
        else:
            logging.info(f"Cache miss for prompt: {prompt}")
            response = await self.openai_service.generate_response(
                prompt, OPENAI_DEFAULT_MODEL, {}
            )
            # Correctly access response attributes for Pydantic models
            text_response = (
                response.choices[0].message.content.strip()
                if response.choices
                else ""
            )
            self.cache.set(prompt_hash, text_response)
            return text_response
