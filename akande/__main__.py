import asyncio
import logging
from .services import OpenAIServiceImpl
from .akande import Akande
from .config import OPENAI_API_KEY


async def main():
    """Main function to initialize and run the Akande voice assistant."""
    if not OPENAI_API_KEY:
        logging.error(
            "Invalid or missing OPENAI_API_KEY in environment variables."
        )
        return

    openai_service = OpenAIServiceImpl(api_key=OPENAI_API_KEY)
    akande = Akande(openai_service=openai_service)
    await akande.run_interaction()


if __name__ == "__main__":
    asyncio.run(main())
