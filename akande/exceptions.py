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


class LLMError(Exception):
    """Raised when an LLM API call fails.

    Attributes:
        user_message: A human-friendly description of the error
            suitable for display in CLI or TUI output.
        original: The underlying exception that triggered the
            failure, if available.
    """

    def __init__(
        self,
        user_message: str,
        original: Exception | None = None,
    ):
        super().__init__(user_message)
        self.user_message = user_message
        self.original = original
