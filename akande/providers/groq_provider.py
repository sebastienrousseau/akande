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


class GroqProvider(OpenAICompatProvider):
    """Groq inference API provider (OpenAI-compatible).

    Env vars: GROQ_API_KEY
    """

    _provider_name = "groq"

    def __init__(self):
        self._api_key = os.getenv("GROQ_API_KEY", "")
        self._base_url = "https://api.groq.com/openai/v1"
        self._default_model = "llama3-8b-8192"
        self._init_client()
