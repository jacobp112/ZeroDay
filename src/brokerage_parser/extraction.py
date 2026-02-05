from pathlib import Path
import fitz  # PyMuPDF
from typing import Dict
import logging

# Configure logger (basic setup, can be moved to main config later)
logger = logging.getLogger(__name__)

def extract_text(pdf_path: Path) -> Dict[int, str]:
    """
    Extracts text from a PDF file using only native extraction (PyMuPDF).

    Compatible with environments without admin rights (no Tesseract/Poppler).
    Logs a warning if a page has very little text (<20 chars), which might indicate a scan.

    Args:
        pdf_path (Path): Path to the PDF file.

    Returns:
        Dict[int, str]: A dictionary mapping page numbers (1-indexed) to extracted text.

    Raises:
        FileNotFoundError: If the pdf_path does not exist.
        Exception: For other errors during extraction.
    """
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    extracted_data = {}

    try:
        doc = fitz.open(pdf_path)

        for page_num, page in enumerate(doc, start=1):
            text = page.get_text()
            stripped_text = text.strip()

            # Simple heuristic: if text is too short, warn user
            char_count = len(stripped_text)
            if char_count < 20:
                logger.warning(
                    f"Page {page_num} has only {char_count} characters. May be blank or scanned."
                )

            extracted_data[page_num] = text

        doc.close()
        return extracted_data

    except Exception as e:
        raise Exception(f"Failed to extract text from {pdf_path}: {str(e)}")
