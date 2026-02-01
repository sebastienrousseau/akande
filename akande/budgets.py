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

"""Performance budget constants (milliseconds).

These targets are used by telemetry logging to warn when a pipeline
stage exceeds its budget and by regression tests to guard against
performance degradation.
"""

TTS_BUDGET_MS = 2000
"""Text-to-speech synthesis budget."""

STT_BUDGET_MS = 3000
"""Speech-to-text recognition budget."""

LLM_BUDGET_MS = 5000
"""LLM provider round-trip budget."""

E2E_BUDGET_MS = 12000
"""End-to-end pipeline budget (question to spoken answer)."""

CACHE_BUDGET_MS = 50
"""Cache lookup budget."""
