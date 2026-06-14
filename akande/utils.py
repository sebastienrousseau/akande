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
import datetime
import logging
import os
import re
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape

from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import (
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
)

from akande.audit import build_manifest, write_sidecar
from akande.profiles import active_profile

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


def strip_markdown(text: str) -> str:
    """
    Remove common markdown formatting from text.

    Strips bold, italic, headings, inline code, and link syntax
    so that text reads cleanly for TTS, PDF, and plain-text output.

    Parameters
    ----------
    text : str
        The markdown-formatted text.

    Returns
    -------
    str
        Plain text with markdown syntax removed.
    """
    # Remove heading prefixes (e.g. "## Heading")
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    # Remove bold/italic markers (**, __, *, _)
    text = re.sub(r"\*{1,2}(.+?)\*{1,2}", r"\1", text)
    text = re.sub(r"_{1,2}(.+?)_{1,2}", r"\1", text)
    # Remove inline code backticks
    text = re.sub(r"`(.+?)`", r"\1", text)
    # Convert [text](url) links to just text
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    return text


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


def validate_api_key(api_key: str | None) -> bool:
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


def _markdown_inline_to_reportlab(text: str) -> str:
    """
    Convert inline markdown to ReportLab XML markup.

    Handles bold, italic, inline code, and links.  The input
    must already be XML-escaped so that user content cannot
    inject ReportLab tags.

    Parameters
    ----------
    text : str
        An XML-escaped line of text that may contain markdown.

    Returns
    -------
    str
        Text with markdown replaced by ReportLab markup.
    """
    # Bold: **text** or __text__
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"__(.+?)__", r"<b>\1</b>", text)
    # Italic: *text* or _text_  (single markers)
    text = re.sub(r"\*(.+?)\*", r"<i>\1</i>", text)
    text = re.sub(r"(?<!\w)_(.+?)_(?!\w)", r"<i>\1</i>", text)
    # Inline code: `text`
    text = re.sub(
        r"`(.+?)`",
        r'<font name="Courier">\1</font>',
        text,
    )
    # Links: [text](url) → text
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    return text


def _maybe_sign_briefing(
    *,
    pdf_path,
    question: str,
    response: str,
    provider: str,
    model: str,
    correlation_id: str | None,
) -> None:
    """Write an Ed25519-signed audit sidecar when the profile requires it.

    Lives next to :func:`generate_pdf` so the signing decision rides
    with the PDF artefact.  Quietly does nothing when the active
    profile has ``audit_signing`` disabled (the default ``local``
    profile) — existing v0.0.5 behaviour is unchanged.
    """
    try:
        profile = active_profile()
        if not profile.audit_signing:
            return
        manifest = build_manifest(
            prompt=question,
            response=response,
            provider=provider,
            model=model,
            profile=profile.name,
            correlation_id=correlation_id,
        )
        write_sidecar(manifest, pdf_path)
    except Exception:
        # Audit signing must never block briefing delivery; log
        # and continue.
        logging.error(
            "Audit signing failed",
            exc_info=True,
            extra={"event": "Audit:SigningFailed"},
        )


def generate_pdf(
    question: str,
    response: str,
    *,
    provider: str = "openai",
    model: str = "",
    correlation_id: str | None = None,
) -> str:
    """
    Generates a PDF document containing a question and response.

    Markdown in *response* is converted to proper ReportLab
    formatting: headings become styled headings, bold/italic
    become ``<b>``/``<i>`` tags, and bullet lists use the list
    item style.

    When the active operational profile (see :mod:`akande.profiles`)
    has ``audit_signing`` enabled — i.e. ``AKANDE_PROFILE=eu`` or
    ``strict`` — an Ed25519-signed audit sidecar
    (``<pdf>.audit.json``) is written next to the PDF.  The sidecar
    contains the model + provider, the prompt and response hashes,
    a timestamp, and the signature; verify it with
    ``akande verify-pdf <path>``.

    Parameters
    ----------
    question : str
        The question to be included in the PDF.
    response : str
        The response to the question (may contain markdown).
    provider, model:
        Recorded in the audit manifest when signing is on.  Optional
        because the unsigned (``local``) path is unchanged.
    correlation_id:
        Carried through the audit log so the sidecar can be
        correlated with structured log entries.
    """
    try:
        directory_path = get_output_directory()
        filename = get_output_filename(".pdf")
        file_path = directory_path / filename

        doc = SimpleDocTemplate(str(file_path), pagesize=letter)
        flowables = []

        # Optional: Add a logo at the top if the file exists
        logo_path = Path(__file__).resolve().parent.parent / "512x512.png"
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
            stripped = para.strip()
            if not stripped:
                continue

            # Detect markdown heading (## …)
            heading_match = re.match(
                r"^#{1,6}\s+(.*)", stripped
            )
            if heading_match:
                heading_text = xml_escape(
                    heading_match.group(1)
                )
                flowables.append(
                    Paragraph(heading_text, _heading2_style)
                )
                flowables.append(Spacer(1, 6))
                continue

            # Detect known section keywords as headings
            if stripped.startswith(
                (
                    "Overview",
                    "Solution",
                    "Conclusion",
                    "Recommendations",
                )
            ):
                safe_para = _markdown_inline_to_reportlab(
                    xml_escape(stripped)
                )
                flowables.append(
                    Paragraph(safe_para, _heading2_style)
                )
                flowables.append(Spacer(1, 6))
                continue

            # Detect bullet / numbered list items
            if re.match(r"^[-*]\s", stripped):
                item_text = stripped[2:]
                safe_item = _markdown_inline_to_reportlab(
                    xml_escape(item_text)
                )
                flowables.append(
                    Paragraph(
                        "- " + safe_item, _list_item_style
                    )
                )
                flowables.append(Spacer(1, 6))
                continue

            if re.match(r"^\d+[.)]\s", stripped):  # pragma: no cover - exercised in integration
                safe_para = _markdown_inline_to_reportlab(
                    xml_escape(stripped)
                )
                flowables.append(
                    Paragraph(safe_para, _list_item_style)
                )
                flowables.append(Spacer(1, 6))
                continue

            # Regular paragraph — convert inline markdown
            safe_para = _markdown_inline_to_reportlab(
                xml_escape(stripped)
            )
            flowables.append(
                Paragraph(safe_para, _paragraph_style)
            )
            flowables.append(Spacer(1, 6))

        doc.build(flowables)
        try:
            os.chmod(str(file_path), 0o600)
        except OSError:  # pragma: no cover - filesystem-specific
            pass
        logging.info(
            "PDF generated",
            extra={
                "event": "Export:PDFGenerated",
                "extra_data": {"file_path": str(file_path)},
            },
        )
        _maybe_sign_briefing(
            pdf_path=file_path,
            question=question,
            response=response,
            provider=provider,
            model=model,
            correlation_id=correlation_id,
        )
        return str(file_path)
    except Exception as e:  # pragma: no cover - logged + returns ""
        logging.error(
            f"PDF generation failed: {type(e).__name__}: {e}",
            exc_info=True,
            extra={"event": "Export:PDFFailed"},
        )
        return ""


def generate_csv(question: str, response: str) -> str:
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

        try:
            os.chmod(str(file_path), 0o600)
        except OSError:  # pragma: no cover - filesystem-specific
            pass
        logging.info(
            "CSV generated",
            extra={
                "event": "Export:CSVGenerated",
                "extra_data": {"file_path": str(file_path)},
            },
        )
        return str(file_path)
    except Exception as e:  # pragma: no cover - logged + returns ""
        logging.error(
            f"CSV generation failed: {type(e).__name__}: {e}",
            exc_info=True,
            extra={"event": "Export:CSVFailed"},
        )
        return ""
