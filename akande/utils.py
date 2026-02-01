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
import csv
from typing import Optional
from xml.sax.saxutils import escape as xml_escape
from reportlab.lib.pagesizes import letter
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Image,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from pathlib import Path
import datetime
import logging
import re

# Module-level cached styles for PDF generation
_styles = getSampleStyleSheet()

_list_item_style = ParagraphStyle(
    "listItem",
    parent=_styles["BodyText"],
    fontSize=12,
    leading=14,
    spaceBefore=0,
    spaceAfter=6,
    leftIndent=10,
    firstLineIndent=-10,
)

_heading1_style = _styles["Heading1"]
_heading1_style.fontName = "Helvetica-Bold"
_heading1_style.fontSize = 14
_heading1_style.leading = 16
_heading1_style.alignment = TA_LEFT

_heading2_style = _styles["Heading2"]
_heading2_style.fontName = "Helvetica-Bold"
_heading2_style.fontSize = 12
_heading2_style.leading = 14
_heading2_style.alignment = TA_LEFT

_paragraph_style = _styles["BodyText"]
_paragraph_style.fontName = "Helvetica"
_paragraph_style.fontSize = 12
_paragraph_style.leading = 14
_paragraph_style.alignment = TA_LEFT


def get_output_directory() -> Path:
    """
    Get or create the date-stamped output directory.

    Returns
    -------
    Path
        The path to the output directory for today's date.
    """
    date_str = datetime.datetime.now().strftime("%Y-%m-%d")
    directory_path = Path(date_str)
    directory_path.mkdir(parents=True, exist_ok=True)
    return directory_path


def get_output_filename(extension: str) -> str:
    """
    Generate a timestamped output filename with seconds precision.

    Parameters
    ----------
    extension : str
        The file extension (e.g., '.pdf', '.csv', '.wav', '.log').

    Returns
    -------
    str
        The generated filename.
    """
    return (
        datetime.datetime.now().strftime(
            "%Y-%m-%d-%H-%M-%S-Akande"
        )
        + extension
    )


def validate_api_key(api_key: Optional[str]) -> bool:
    """
    Validates the format of an OpenAI API key.

    Parameters
    ----------
    api_key : Optional[str]
        The API key to validate.

    Returns
    -------
    bool
        True if the API key format is valid, False otherwise.
    """
    if api_key is None or len(api_key) < 20:
        return False
    valid_prefixes = ("sk-", "sk-proj-", "sk-org-")
    return api_key.startswith(valid_prefixes)


def generate_pdf(question: str, response: str) -> None:
    """
    Generates a PDF document containing a question and response.

    Parameters
    ----------
    question : str
        The question to be included in the PDF.
    response : str
        The response to the question.
    """
    try:
        directory_path = get_output_directory()
        filename = get_output_filename(".pdf")
        file_path = directory_path / filename

        doc = SimpleDocTemplate(str(file_path), pagesize=letter)
        flowables = []

        # Optional: Add a logo at the top if the file exists
        logo_path = Path("./512x512.png")
        if logo_path.exists():
            logo = Image(str(logo_path), width=48, height=48)
            logo.hAlign = "RIGHT"
            logo.preserveAspectRatio = True
            flowables.append(logo)
            flowables.append(Spacer(1, 12))

        # Escape user input to prevent ReportLab markup injection
        safe_question = xml_escape(question.title())
        flowables.append(
            Paragraph(safe_question, _heading1_style)
        )
        flowables.append(Spacer(1, 6))

        # Process and format the response content
        paragraphs = response.split("\n")
        for para in paragraphs:
            safe_para = xml_escape(para)
            if para.startswith(
                (
                    "Overview",
                    "Solution",
                    "Conclusion",
                    "Recommendations",
                )
            ):
                flowables.append(
                    Paragraph(safe_para, _heading2_style)
                )
                flowables.append(Spacer(1, 6))
            elif re.match(r"^-?\d", para):
                formatted_text = (
                    "- " + safe_para
                    if not safe_para.startswith("-")
                    else safe_para
                )
                flowables.append(
                    Paragraph(formatted_text, _list_item_style)
                )
                flowables.append(Spacer(1, 6))
            else:
                flowables.append(
                    Paragraph(safe_para, _paragraph_style)
                )
                flowables.append(Spacer(1, 6))

        doc.build(flowables)
        logging.info(
            "PDF generated",
            extra={
                "event": "Export:PDFGenerated",
                "extra_data": {"file_path": str(file_path)},
            },
        )
    except Exception as e:
        logging.error(
            f"PDF generation failed: {type(e).__name__}: {e}",
            exc_info=True,
            extra={"event": "Export:PDFFailed"},
        )


def generate_csv(question: str, response: str) -> None:
    """
    Generates a CSV document containing a question and response.

    Parameters
    ----------
    question : str
        The question to be included in the CSV.
    response : str
        The response to the question.
    """
    try:
        directory_path = get_output_directory()
        filename = get_output_filename(".csv")
        file_path = directory_path / filename

        with open(
            file_path, mode="w", newline="", encoding="utf-8"
        ) as file:
            csv_writer = csv.writer(file)
            csv_writer.writerow(["Question", "Response"])
            csv_writer.writerow([question, response])

        logging.info(
            "CSV generated",
            extra={
                "event": "Export:CSVGenerated",
                "extra_data": {"file_path": str(file_path)},
            },
        )
    except Exception as e:
        logging.error(
            f"CSV generation failed: {type(e).__name__}: {e}",
            exc_info=True,
            extra={"event": "Export:CSVFailed"},
        )
