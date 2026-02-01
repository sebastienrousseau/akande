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


class ProviderMessage:
    """Normalised message matching OpenAI's response format."""

    __slots__ = ("content",)

    def __init__(self, content: str):
        self.content = content


class ProviderChoice:
    """Normalised choice matching OpenAI's response format."""

    __slots__ = ("message",)

    def __init__(self, message: ProviderMessage):
        self.message = message


class ProviderResponse:
    """Normalised response wrapper for non-OpenAI providers.

    Provides a `.choices[0].message.content` interface matching
    the OpenAI SDK response format so that the rest of the
    application can consume any provider's output uniformly.
    """

    __slots__ = ("choices",)

    def __init__(self, content: str):
        self.choices = [
            ProviderChoice(ProviderMessage(content))
        ]
