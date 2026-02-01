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


class LMStudioProvider(OpenAICompatProvider):
    """LM Studio local inference provider (OpenAI-compatible).

    Env vars: LMSTUDIO_HOST (default: http://localhost:1234)
    """

    _provider_name = "lmstudio"

    def __init__(self):
        host = os.getenv(
            "LMSTUDIO_HOST", "http://localhost:1234"
        )
        self._api_key = "lm-studio"
        self._base_url = f"{host}/v1"
        self._default_model = "local-model"
        self._init_client()
