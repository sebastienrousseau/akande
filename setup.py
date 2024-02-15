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
from pathlib import Path
from setuptools import setup, find_packages
import sys

# Define the directory where setup.py is located
this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text()

# Read the contents of your requirements.txt
requirements_path = this_directory / "requirements.txt"
with open(requirements_path, "r") as file:
    requirements = file.read().splitlines()

# Conditional dependency
conditional_requirements = []
if sys.platform == 'darwin':
    conditional_requirements.extend([
        'pyobjc-core==9.0.1',
    ])

setup(
    author="Sebastian Rousseau",
    author_email="sebastian.rousseau@gmail.com",
    description="""
        Akande: A versatile voice assistant powered by OpenAI's GPT-3. It
        offers both voice and text interaction, leveraging advanced speech
        recognition and text-to-speech capabilities for a wide range of tasks.
    """,
    long_description=long_description,
    long_description_content_type="text/markdown",
    license="Apache Software License",
    name="akande",
    version="0.0.3",
    url="https://github.com/sebastienrousseau/akande",
    packages=find_packages(),
    install_requires=requirements,
    python_requires=">=3.7",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: Apache Software License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
    ],
)
