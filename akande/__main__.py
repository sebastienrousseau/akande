import asyncio
import os
import logging
import sys
import hashlib
import sqlite3
import threading
from datetime import datetime, timedelta
from typing import Any, Dict, Optional
from abc import ABC, abstractmethod
import time
from dotenv import load_dotenv
import openai
import speech_recognition as sr
from pydub import AudioSegment
from pydub.playback import play
from gtts import gTTS
import tempfile
from concurrent.futures import ThreadPoolExecutor
from reportlab.lib.pagesizes import letter
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Image,
)
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY


# Load environment variables
load_dotenv()

# Configuration
DEFAULT_MODEL = os.getenv(
    "OPENAI_DEFAULT_MODEL", "gpt-3.5-turbo-instruct"
)
API_CALL_TIMEOUT = 30  # Timeout for API calls in seconds

logging.basicConfig(
    filename="akande_metrics.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)


def validate_api_key(api_key: Optional[str]) -> bool:
    """Validate the OpenAI API key format."""
    return api_key is not None and len(api_key) > 20


class SQLiteCache:
    def __init__(
        self,
        db_path: str,
        max_size: int = 1000,
        expiration: timedelta = timedelta(days=7),
    ):
        self.db_path = db_path
        self.max_size = max_size
        self.expiration = expiration
        self.lock = threading.Lock()
        self.initialize_cache()

    def initialize_cache(self):
        with self.lock, sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS cache (
                    prompt_hash TEXT PRIMARY KEY,
                    response TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """
            )
            conn.commit()

    def get(self, prompt_hash: str) -> Optional[str]:
        start_time = time.time()
        with self.lock, sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                    SELECT response
                    FROM cache
                    WHERE prompt_hash = ?
                    AND timestamp > ?
                """,
                (prompt_hash, datetime.now() - self.expiration),
            )
            result = cursor.fetchone()
            hit_miss = "hit" if result else "miss"
            latency = (
                time.time() - start_time
            ) * 1000  # Convert to milliseconds
            logging.info(
                f"""
                    Cache {hit_miss}
                    for {prompt_hash}.
                    Access latency: {latency:.2f} ms
                """
            )
            return result[0] if result else None

    def set(self, prompt_hash: str, response: str):
        with self.lock, sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "REPLACE INTO cache (prompt_hash, response) VALUES (?, ?)",
                (prompt_hash, response),
            )
            cursor.execute(
                """
                    DELETE FROM cache
                    WHERE timestamp <= (SELECT timestamp
                    FROM cache
                    ORDER BY timestamp DESC LIMIT 1 OFFSET ?)
                """,
                (self.max_size,),
            )
            conn.commit()


class OpenAIService(ABC):
    """Base class for all OpenAI services."""

    @abstractmethod
    async def generate_response(
        self, prompt: str, model: str, parameters: Dict[str, Any]
    ) -> str:
        pass


class OpenAIServiceImpl(OpenAIService):
    """Implementation of the OpenAI service."""

    def __init__(self, api_key: str, rate_limit: int = 60) -> None:
        self.api_key = api_key
        self.rate_limit = rate_limit
        openai.api_key = api_key
        self.requests_count = 0
        self.backoff_factor = 1
        self.executor = ThreadPoolExecutor(max_workers=4)

    async def generate_response(
        self,
        prompt: str,
        model: str = DEFAULT_MODEL,
        parameters: Dict[str, Any] = {},
    ) -> str:
        pre_prompt = """
            As an AI assistant, your primary role is to help users find
            comprehensive and accurate information on a variety of topics and
            present this information in the form of an executive summary.
            When a query is received:
            1. Conduct a thorough search across multiple sources to gather
            diverse perspectives, ensuring the information is up-to-date and
            relevant.
            2. Synthesize your findings into a concise executive summary of
            maximum 150 words. The summary should be tailored to the needs of
            focusing on the most critical points, key findings, and actionable
            insights.
            3. Ensure your response is structured logically, with a clear
            introduction, body, and conclusion. Use headings or bullet points
            to enhance readability and facilitate quick scanning.
            4. Write in clear, straightforward language, avoiding jargon and
            technical terms that may not be familiar to all executives. If
            technical terms are necessary, provide brief explanations.

            Remember, your goal is to empower the reader with succinct,
            actionable information, enabling them to make informed decisions
            quickly. Your response should be an executive summary that is
            comprehensive yet concise, tailored to the needs of high-level
            decision-makers.
            """
        combined_prompt = pre_prompt + "\n\n" + prompt

        if "max_tokens" not in parameters:
            parameters["max_tokens"] = 1024
        if not validate_api_key(self.api_key):
            logging.error(
                "Invalid API Key: %s", {"api_key": self.api_key}
            )
            return "Invalid API Key."
        if self.requests_count >= self.rate_limit:
            wait_time = 60 * self.backoff_factor
            logging.warning(
                "Rate limit reached, waiting %s",
                {"wait_time": wait_time},
            )
            await asyncio.sleep(wait_time)
            self.backoff_factor = min(self.backoff_factor * 2, 64)
            self.requests_count = 0
        try:
            start_time = time.time()
            response = await asyncio.get_event_loop().run_in_executor(
                self.executor,
                lambda: openai.Completion.create(
                    engine=model, prompt=combined_prompt, **parameters
                ),
            )
            latency = (
                time.time() - start_time
            ) * 1000  # Convert to milliseconds
            logging.info(
                f"OpenAI API response latency: {latency:.2f} ms"
            )
            response_text = response.choices[0].text.strip()
            self.requests_count += 1
            self.backoff_factor = 1
            return response_text
        except asyncio.TimeoutError:
            logging.error("OpenAI API call timed out")
            return "Sorry, the request timed out. Please try again."
        except openai.OpenAIError as e:
            logging.error("OpenAI API error %s", {"error": str(e)})
            return (
                "Sorry, I'm having some trouble connecting right now."
            )


class Akande:
    """The Akande voice assistant."""

    def __init__(self, openai_service: OpenAIService):
        self.openai_service = openai_service
        self.recognizer = sr.Recognizer()
        self.cache = SQLiteCache("akande_cache.db")

    def hash_prompt(self, prompt: str) -> str:
        """Hash the prompt for caching."""
        return hashlib.sha256(prompt.encode("utf-8")).hexdigest()

    async def speak(self, text: str) -> None:
        """Speak the given text using gTTS and play the audio."""
        try:
            with tempfile.NamedTemporaryFile(
                suffix=".mp3", delete=True
            ) as tmpfile:
                tts = gTTS(text=text, lang="en")
                tts.save(tmpfile.name)
                sound = AudioSegment.from_file(tmpfile.name)
                play(sound)
        except Exception as e:
            logging.error(
                "Error using gTTS for speech synthesis %s",
                {"error": str(e)},
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
            logging.error(
                "Speech recognition service error %s", {"error": str(e)}
            )
            await self.speak(
                """
                    I'm sorry, I encountered an error with the speech
                    recognition service.
                """
            )
            return ""

    async def run_interaction(self) -> None:
        """Main interaction loop of the voice assistant."""
        while True:  # Loop to allow multiple interactions.
            # Prompt the user for their preferred input method
            # at the start of each interaction.
            choice = input(
                """
Welcome to Akande, your AI voice assistant.

Press Enter to use voice or type your question and press Enter:
"""
            ).strip()

            # Initialize prompt to None to check later if it has been set.
            prompt = None

            # If the user types a question or command, use it directly.
            if choice:
                if choice.lower() == "stop":
                    print("\nGoodbye!")
                    break
                prompt = choice

            # If the user presses Enter without typing,
            # switch to listening for voice input.
            else:
                print("Listening...")
                prompt = await self.listen()
                if prompt and prompt.lower() == "stop":
                    print("\nGoodbye!")
                    break

            # If a "stop" command hasn't been issued, proceed with generating
            # and speaking the response.
            if prompt and prompt.lower() not in [
                "stop voice",
                "stop text",
                "thank you for your help",
            ]:
                response = await self.generate_response(
                    prompt
                )  # Generate response based on the input.
                await self.speak(response)
                # Call generate_pdf here to create a PDF of the interaction
                await self.generate_pdf(prompt, response)

            elif prompt.lower() == "thank you for your help":
                await self.speak("You're welcome. Goodbye!")
                break  # Exit the loop to end the interaction gracefully.

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
                prompt, DEFAULT_MODEL, {}
            )
            self.cache.set(prompt_hash, response)
            return response

    async def generate_pdf(self, question: str, response: str) -> None:
        filename = (
            datetime.now().strftime("%Y-%m-%d-%H-%M-Akande") + ".pdf"
        )

        # Create the document with SimpleDocTemplate for text content
        doc = SimpleDocTemplate(filename, pagesize=letter)
        styles = getSampleStyleSheet()
        flowables = []

        # Define custom styles for header and response
        custom_header_style = ParagraphStyle(
            "CustomHeader",
            parent=styles["Heading1"],
            fontSize=24,
            leading=28,
            alignment=TA_CENTER,
            fontName="Helvetica-Bold",
        )

        custom_response_style = ParagraphStyle(
            "CustomResponse",
            parent=styles["BodyText"],
            fontSize=17,
            leading=21,
            alignment=TA_JUSTIFY,
            fontName="Helvetica",
        )

        # Logo as an Image flowable
        logo_path = "./130x130.png"
        logo = Image(logo_path, 130, 130)
        logo.hAlign = "CENTER"
        flowables.append(logo)
        flowables.append(Spacer(1, 12))

        # Add header and response as Paragraph flowables
        flowables.append(
            Paragraph(question.upper(), custom_header_style)
        )
        flowables.append(
            Spacer(1, 12)
        )  # Space between header and response
        flowables.append(Paragraph(response, custom_response_style))

        # Build the document with the flowables
        doc.build(flowables)

        print(f"PDF generated: {filename}")


async def main():
    """Main function to initialize and run the Akande voice assistant."""
    api_key = os.getenv("GPT3_API_KEY")
    if not validate_api_key(api_key):
        logging.error(
            "Invalid or missing GPT3_API_KEY in environment variables %s",
            {"api_key": api_key},
        )
        sys.exit(1)
    openai_service = OpenAIServiceImpl(api_key)
    akande = Akande(openai_service)
    await akande.run_interaction()


if __name__ == "__main__":
    asyncio.run(main())
