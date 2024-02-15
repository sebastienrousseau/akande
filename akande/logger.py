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
import logging


def basic_config(filename: str, level: int, log_format: str) -> None:
    """
    This function sets up the logging configuration for the application.

    :param filename: The name of the log file.
    :param level: The logging level.
    :param log_format: The format of the log messages.
    :return: None
    """
    logging.basicConfig(
        filename=filename, level=level, format=log_format
    )
