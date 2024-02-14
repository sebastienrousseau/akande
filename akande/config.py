import os
from dotenv import load_dotenv

# Loads environment variables from a .env file into the environment.
load_dotenv()

# Configuration

# Number of seconds allowed per API call before timing out.
API_CALL_TIMEOUT = 90

# Gets OpenAI API key from the environment variables loaded by load_dotenv().
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Gets the name of default OpenAI model to use from the environment variables
OPENAI_DEFAULT_MODEL = os.getenv("OPENAI_DEFAULT_MODEL")
