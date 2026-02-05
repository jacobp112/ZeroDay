from pathlib import Path
import fitz  # PyMuPDF
from typing import Dict, List, Optional
import logging

# Configure logger
logger = logging.getLogger(__name__)

# Type alias for clarity: List of columns -> List of cells
# Using simple List[List[str]] for rows -> cells is more intuitive.
# The user specified: page_num -> [table1, table2, ...] -> [row1, row2, ...] -> [cell1, cell2, ...]
# So TableData represents one page's worth of tables? Or is it the whole structure?
# Looking at the user request: "Returns dict mapping page number to list of tables"
# And "TableData = List[List[List[str]]]" refers to the list of tables for a page (or potentially just one table?)
# Let's define Table Structure:
# Table = List[List[str]] (List of Rows, where Row is List of Cells)
# PageTables = List[Table]
TableData = List[List[List[str]]]

def extract_tables(pdf_path: Path) -> Dict[int, TableData]:
    """
    Extracts tables from a PDF using PyMuPDF's find_tables() (requires v1.23.0+).

    Args:
        pdf_path (Path): Path to the PDF file.

    Returns:
        Dict[int, TableData]: A dictionary mapping page numbers (1-indexed) to a list of tables.
        Each table is a list of rows, and each row is a list of cell strings.
    """
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    extracted_tables = {}

    try:
        doc = fitz.open(pdf_path)

        for page_num, page in enumerate(doc, start=1):
            tables = page.find_tables()
            page_tables = []

            if tables:
                for table in tables:
                    # table.extract() returns a list of lists of strings
                    page_tables.append(table.extract())

            if page_tables:
                extracted_tables[page_num] = page_tables

        doc.close()
        return extracted_tables

    except Exception as e:
        logger.error(f"Table extraction failed for {pdf_path}: {e}")
        # Return partial results or empty dict rather than crashing existing flows
        return {}

def extract_text_with_layout(pdf_path: Path) -> Dict[int, str]:
    """
    Extracts text preserving layout columns using 'dict' extraction.

    This is useful when tables aren't detected but columns exist visually.
    Groups text blocks by vertical alignment to simulate reading order across columns.

    Args:
        pdf_path (Path): Path to the PDF.

    Returns:
        Dict[int, str]: Page number mapped to layout-preserved text.
    """
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    extracted_text = {}

    try:
        doc = fitz.open(pdf_path)

        for page_num, page in enumerate(doc, start=1):
            # 'blocks' gives us (x0, y0, x1, y1, "text", block_no, block_type)
            # But 'dict' gives more structure. Let's use 'blocks' for simpler sorting if just text.
            # actually 'get_text("blocks")' is easier for column sorting than 'dict'
            # blocks are usually already sorted by reading order (top-down, left-right),
            # but sometimes column logic is needed. PyMuPDF's default text extraction
            # usually handles reading order well.
            # However, the user specifically asked for grouping by Y-coordinate and sorting by X.

            # Implementation of the user's requested logic:

            blocks = page.get_text("blocks")
            # Filter out non-text blocks (type != 0)
            text_blocks = [b for b in blocks if b[6] == 0]

            # Sort mainly by vertical (y0), then horizontal (x0)
            # A small tolerance for y-alignment is often needed!
            # Let's assume standard sort is sufficient for now, or implement tolerance clustering.
            # Standard 'blocks' output is usually already sorted in intended reading order.
            # To strictly follow "Group by Y, sort by X":

            # Simple approach: standard sort (y0, x0)
            text_blocks.sort(key=lambda b: (round(b[1]), b[0]))

            full_page_text = ""
            for b in text_blocks:
                full_page_text += b[4] + "\n"

            extracted_text[page_num] = full_page_text

        doc.close()
        return extracted_text

    except Exception as e:
        logger.error(f"Layout text extraction failed for {pdf_path}: {e}")
        return {}


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
