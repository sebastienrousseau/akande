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
from ._openai_compat import OpenAICompatProvider


class OpenAIProvider(OpenAICompatProvider):
    """OpenAI API provider.

    Env vars: OPENAI_API_KEY, OPENAI_DEFAULT_MODEL
    """

    _provider_name = "openai"

    def __init__(self):
        from akande.config import (
            OPENAI_API_KEY,
            OPENAI_DEFAULT_MODEL,
        )

        self._api_key = OPENAI_API_KEY or ""
        self._base_url = ""
        self._default_model = (
            OPENAI_DEFAULT_MODEL or "gpt-3.5-turbo"
        )
        self._init_client()
