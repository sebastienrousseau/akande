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
