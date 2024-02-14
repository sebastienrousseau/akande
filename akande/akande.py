import asyncio
from concurrent.futures import ThreadPoolExecutor
import speech_recognition as sr
import pyttsx4
import hashlib
from datetime import datetime
from functools import partial
from pathlib import Path
from .services import OpenAIService
from .cache import SQLiteCache
from .utils import generate_pdf, generate_csv
from .config import OPENAI_DEFAULT_MODEL
import logging


class Akande:
    """The Akande voice assistant.

    This class represents the voice assistant capable of understanding and
    responding to user queries. It integrates speech recognition and synthesis,
    leveraging OpenAI's GPT models for generating responses.
    """

    def __init__(self, openai_service: OpenAIService):
        """
        Initialize the voice assistant with necessary services and settings.
        """
        self.openai_service = openai_service
        self.recognizer = sr.Recognizer()
        self.cache = SQLiteCache("akande_cache.db")
        self.executor = ThreadPoolExecutor(max_workers=4)

    def hash_prompt(self, prompt: str) -> str:
        """Hash the prompt for caching."""
        return hashlib.sha256(prompt.encode("utf-8")).hexdigest()

    async def speak(self, text: str) -> None:
        """
        Speak the given text using pyttsx3 in an asynchronous manner.
        This method utilizes a ThreadPoolExecutor to run pyttsx3's blocking
        operations in a separate thread, allowing the asyncio event loop to
        remain responsive.
        """

        def tts_engine_run(text: str):
            """
            Generates a WAV file from the given text using pyttsx3.

            This function initializes a text-to-speech engine, sets its
            properties, and saves the spoken text as a WAV file in a directory
            named with the current date (%Y-%m-%d).

            The filename is timestamped to ensure uniqueness.

            Parameters:
            - text (str): The text to be converted to speech.

            Notes:
            - The WAV file is saved in a directory corresponding to the
            current date within the current working directory.
            The directory and file names are based on the current date and
            time.
            - If an error occurs during speech synthesis, it is logged as an
            error.
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
            file_path = (
                directory_path / filename
            )  # This is the full path for the new WAV file

            try:
                engine = pyttsx4.init()
                engine.setProperty("rate", 161)
                engine.say(text)
                engine.save_to_file(text, str(file_path))
                engine.runAndWait()
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
            welcome_msg = "\nWelcome to Àkàndé, your AI voice assistant.\n"
            instructions = "\nPress Enter to use voice or type " \
                "your question and press Enter:\n"
            choice = (
                input(welcome_msg + instructions)
                .strip()
                .lower()
            )  # Normalize input to lower case immediately

            if choice == "stop":
                print("\nGoodbye!")
                break

            if choice:
                prompt = choice
            else:
                print("Listening...")
                prompt = (
                    await self.listen()
                ).lower()  # Normalize prompt to lower case
                if prompt == "stop":
                    print("\nGoodbye!")
                    break

            if prompt and prompt not in [
                "stop voice",
                "stop text",
                "thank you for your help",
            ]:
                response = await self.generate_response(prompt)
                await self.speak(response)
                await generate_pdf(prompt, response)
                await generate_csv(prompt, response)
            elif prompt == "thank you for your help":
                await self.speak("You're welcome. Goodbye!")
                break

    async def generate_response(self, prompt: str) -> str:
        """Generate a response using the OpenAI service or cache."""
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
            self.cache.set(prompt_hash, response)
            return response
