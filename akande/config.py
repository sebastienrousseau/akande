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

# LLM provider to use (default: "openai"). See akande/providers/ for options.
# Available: openai, anthropic, google, ollama, azure_openai, mistral,
#            cohere, huggingface, groq, lmstudio
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai")

# Optional shared API key for the Web/HTTP surface.  When set, callers
# must supply the same value in the ``X-Akande-Key`` request header on
# every ``/api/*`` route.  Leave unset for purely local development; the
# server logs a startup warning in that case.
AKANDE_API_KEY = os.getenv("AKANDE_API_KEY")

# Optional Redis URL for distributed rate limiting.  When set, the
# server uses a Redis-backed sliding-window limiter so multiple
# instances share state.  Falls back to in-memory if Redis is
# unreachable (with a warning log).
REDIS_URL = os.getenv("REDIS_URL")
