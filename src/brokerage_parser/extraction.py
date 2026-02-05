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


def detect_implicit_columns(lines: List[str], min_gap: int = 3, min_lines: int = 5) -> List[int]:
    """
    Detect column boundaries by finding consistent whitespace gaps.

    Analyzes character positions across multiple lines to find X-positions
    where whitespace consistently appears, indicating column separations.

    Args:
        lines: Text lines to analyze
        min_gap: Minimum consecutive spaces to consider a gap
        min_lines: Minimum lines that must have gap at same position

    Returns:
        List of X positions where columns split (sorted)
    """
    if not lines or len(lines) < min_lines:
        return []

    # Filter out empty/very short lines
    valid_lines = [line for line in lines if len(line.strip()) > 10]
    if len(valid_lines) < min_lines:
        return []

    # Find the max line length to establish the analysis width
    max_len = max(len(line) for line in valid_lines)
    if max_len < 20:
        return []

    # For each position, count how many lines have a space there
    # A column gap is where most lines have spaces
    space_counts = [0] * max_len

    for line in valid_lines:
        padded = line.ljust(max_len)
        for i, char in enumerate(padded):
            if char == ' ':
                space_counts[i] += 1

    # Find regions where most lines (>= threshold) have spaces
    threshold = len(valid_lines) * 0.7  # 70% of lines must have space

    # Find gap regions (consecutive positions where space_count >= threshold)
    gap_regions = []  # List of (start, end) tuples
    in_gap = False
    gap_start = 0

    for i, count in enumerate(space_counts):
        if count >= threshold:
            if not in_gap:
                gap_start = i
                in_gap = True
        else:
            if in_gap:
                gap_end = i
                gap_length = gap_end - gap_start
                if gap_length >= min_gap:
                    gap_regions.append((gap_start, gap_end))
                in_gap = False

    # Don't add gap at end - trailing spaces are not column boundaries

    # Convert gap regions to column boundaries
    # Use the start of each gap as the split point
    # Skip the first gap if it starts at position 0 (leading whitespace)
    # Also skip gaps that would result in very narrow final columns
    column_boundaries = []
    for start, end in gap_regions:
        if start > 0 and end < max_len - 2:  # Skip leading whitespace and trailing gaps
            column_boundaries.append(start)

    return column_boundaries


def split_line_by_columns(line: str, column_positions: List[int]) -> List[str]:
    """
    Split a single line into cells based on detected column positions.

    Args:
        line: The text line to split
        column_positions: List of X positions where columns split

    Returns:
        List of cell strings (stripped of whitespace)
    """
    if not column_positions:
        return [line.strip()] if line.strip() else []

    cells = []
    prev_pos = 0

    for pos in column_positions:
        if pos <= len(line):
            cell = line[prev_pos:pos].strip()
            cells.append(cell)
            prev_pos = pos
        else:
            # Line is shorter than expected column position
            cell = line[prev_pos:].strip() if prev_pos < len(line) else ""
            cells.append(cell)
            prev_pos = len(line)

    # Add remaining content after last column boundary
    if prev_pos < len(line):
        cells.append(line[prev_pos:].strip())
    else:
        cells.append("")

    return cells


def text_to_implicit_table(text: str, min_gap: int = 3, min_lines: int = 5) -> List[List[str]]:
    """
    Convert raw text to a table structure using implicit column detection.

    Combines detect_implicit_columns() and split_line_by_columns() to
    produce a table in the same format as find_tables() output.

    Args:
        text: Raw text with layout preserved
        min_gap: Minimum consecutive spaces to consider a gap
        min_lines: Minimum lines that must have gap at same position

    Returns:
        Table as list of rows, where each row is list of cell strings.
        Returns empty list if no columns detected or text is not tabular.
    """
    if not text or not text.strip():
        return []

    lines = text.split('\n')

    # Filter to non-empty lines
    non_empty_lines = [line for line in lines if line.strip()]
    if len(non_empty_lines) < min_lines:
        return []

    # Detect column boundaries
    column_positions = detect_implicit_columns(non_empty_lines, min_gap, min_lines)

    if not column_positions:
        # No columns detected - text is not tabular
        return []

    # Split each line by detected columns
    table = []
    for line in non_empty_lines:
        row = split_line_by_columns(line, column_positions)
        # Only include rows that have some content
        if any(cell for cell in row):
            table.append(row)

    # Validate: table should have consistent column count
    if not table:
        return []

    # Normalize column count (pad shorter rows)
    max_cols = max(len(row) for row in table)
    for row in table:
        while len(row) < max_cols:
            row.append("")

    return table

