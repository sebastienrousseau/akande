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

from ._openai_compat import OpenAICompatProvider


class OllamaProvider(OpenAICompatProvider):
    """Ollama local inference provider (OpenAI-compatible API).

    Env vars: OLLAMA_HOST (default: http://localhost:11434)
    """

    _provider_name = "ollama"

    def __init__(self):
        host = os.getenv(
            "OLLAMA_HOST", "http://localhost:11434"
        )
        self._api_key = "ollama"
        self._base_url = f"{host}/v1"
        self._default_model = "llama3"
        self._init_client()
