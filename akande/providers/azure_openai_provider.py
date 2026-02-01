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


class AzureOpenAIProvider(OpenAICompatProvider):
    """Azure OpenAI Service provider.

    Env vars: AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT,
              AZURE_OPENAI_API_VERSION
    """

    _provider_name = "azure_openai"

    def __init__(self):
        import openai
        from akande.config import API_CALL_TIMEOUT

        api_key = os.getenv("AZURE_OPENAI_API_KEY", "")
        endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "")
        api_version = os.getenv(
            "AZURE_OPENAI_API_VERSION", "2024-02-01"
        )

        if not api_key:
            raise ValueError(
                "AZURE_OPENAI_API_KEY environment variable "
                "is required for Azure OpenAI provider."
            )
        if not endpoint:
            raise ValueError(
                "AZURE_OPENAI_ENDPOINT environment variable "
                "is required for Azure OpenAI provider."
            )

        self._api_key = api_key
        self._base_url = endpoint
        self._default_model = "gpt-35-turbo"

        self.client = openai.AzureOpenAI(
            api_key=api_key,
            azure_endpoint=endpoint,
            api_version=api_version,
            timeout=API_CALL_TIMEOUT,
        )
