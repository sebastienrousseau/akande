import csv
from typing import Optional
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
import re


def validate_api_key(api_key: Optional[str]) -> bool:
    """
    Validates the format of an OpenAI API key.

    Checks if the provided API key is not None and its length is greater than
    20 characters, which is a basic validation to ensure that the key has a
    plausible format.

    Parameters:
    - api_key (Optional[str]): The API key to validate.

    Returns:
    - bool: True if the API key is valid, False otherwise.
    """
    return api_key is not None and len(api_key) > 20


async def generate_pdf(question: str, response: str) -> None:
    """
    Generates a PDF document containing a question and its response.

    The PDF will be saved in the current directory.

    Parameters:
    - question (str): The question to be included in the PDF.
    - response (str): The response to the question, to be included in the PDF.

    Returns:
    - None: The function creates a PDF file but does not return any value. It
    prints the filename of the generated PDF.

    Notes:
    - The PDF file is saved in a directory corresponding to the current date
    within the current working directory.
    The directory and file names are based on the current date and time.
    - If an error occurs during speech synthesis, it is logged as an error.
    - The PDF is generated using the reportlab library, which must be installed
    for this function to work.
    - The PDF will contain the question as a header, followed by the response.
    List items are formatted with a dash.
    - The PDF will also contain a logo at the top, if a file
    named "512x512.png" is present in the current directory.
    """
    # Setup directory and file path for the PDF
    date_str = datetime.datetime.now().strftime("%Y-%m-%d")
    directory_path = Path(date_str)
    directory_path.mkdir(parents=True, exist_ok=True)
    filename = (
        datetime.datetime.now().strftime("%Y-%m-%d-%H-%M-Akande")
        + ".pdf"
    )
    file_path = directory_path / filename

    # Initialize the document
    doc = SimpleDocTemplate(str(file_path), pagesize=letter)
    styles = getSampleStyleSheet()

    flowables = []

    # Optional: Add a logo at the top
    logo_path = "./512x512.png"  # Adjust the path to your logo
    logo = Image(logo_path, width=48, height=48)
    logo.hAlign = "RIGHT"
    logo.preserveAspectRatio = True
    flowables.append(logo)
    flowables.append(Spacer(1, 12))

    # Custom style for list items
    list_item_style = ParagraphStyle(
        "listItem",
        parent=styles["BodyText"],
        fontSize=12,
        leading=14,
        spaceBefore=0,
        spaceAfter=6,
        leftIndent=10,
        firstLineIndent=-10,
    )

    # Get the sample style sheet and modify the Heading1 style
    styles = getSampleStyleSheet()
    heading1Style = styles["Heading1"]
    heading1Style.fontName = "Helvetica-Bold"  # Set to a bold font
    heading1Style.fontSize = 14
    heading1Style.leading = 16
    heading1Style.alignment = TA_LEFT  # Set text alignment if needed

    styles = getSampleStyleSheet()
    heading2Style = styles["Heading2"]
    heading2Style.fontName = "Helvetica-Bold"
    heading2Style.fontSize = 12
    heading2Style.leading = 14
    heading2Style.alignment = TA_LEFT  # Set text alignment if needed

    styles = getSampleStyleSheet()
    paragraphStyle = styles["BodyText"]
    paragraphStyle.fontName = "Helvetica"
    paragraphStyle.fontSize = 12
    paragraphStyle.leading = 14
    paragraphStyle.alignment = TA_LEFT  # Set text alignment if needed

    # When adding the question as a header, make sure it's uppercase
    flowables.append(Paragraph(question.title(), heading1Style))
    flowables.append(Spacer(1, 6))

    # Process and format the response content
    paragraphs = response.split("\n")
    for para in paragraphs:
        if para.startswith(
            (
                "Overview",
                "Solution",
                "Conclusion",
                "Recommendations",
            )
        ):
            flowables.append(Paragraph(para, heading2Style))
            flowables.append(Spacer(1, 6))
        elif re.match(r"^-?\d", para):
            formatted_text = (
                "- " + para if not para.startswith("-") else para
            )
            flowables.append(Paragraph(formatted_text, list_item_style))
            flowables.append(Spacer(1, 6))
        else:
            flowables.append(Paragraph(para, paragraphStyle))
            flowables.append(Spacer(1, 6))

    doc.build(flowables)
    print(f"PDF generated: {file_path}")


async def generate_csv(question: str, response: str) -> None:
    """
    Generates a CSV document containing a question and its response.

    This asynchronous function creates a CSV file within a directory named
    with the current date (%Y-%m-%d). The file is named with a timestamp and
    contains two columns: one for the question and one for the response.

    Parameters:
    - question (str): The question to be included in the first column of
    the CSV.
    - response (str): The response to the question, to be included in
    the second column of the CSV.

    Returns:
    - None: The function creates a CSV file but does not return any value.
    It prints the filename of the generated CSV.

    Notes:
    - The CSV file is saved in a directory corresponding to the current date
    within the current working directory.
    The directory and file names are based on the current date and time.
    """
    # Create a directory path with the current date
    date_str = datetime.datetime.now().strftime("%Y-%m-%d")
    directory_path = Path(date_str)
    # Ensure the directory exists
    directory_path.mkdir(parents=True, exist_ok=True)

    # Create the CSV filename with timestamp
    filename = (
        datetime.datetime.now().strftime("%Y-%m-%d-%H-%M-Akande")
        + ".csv"
    )
    file_path = directory_path / filename

    # Open the file in write mode
    with open(
        file_path, mode="w", newline="", encoding="utf-8"
    ) as file:
        csv_writer = csv.writer(file)
        # Write the headers
        csv_writer.writerow(["Question", "Response"])
        # Write the question and response
        csv_writer.writerow([question, response])

    print(f"CSV generated: {file_path}")
