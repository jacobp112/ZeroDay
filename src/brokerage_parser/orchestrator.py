from pathlib import Path
from typing import Optional
import logging
from brokerage_parser.extraction import extract_text, extract_tables, extract_text_with_layout, text_to_implicit_table
from brokerage_parser.detection import detect_broker
from brokerage_parser.parsers import get_parser
from brokerage_parser.models import ParsedStatement

logger = logging.getLogger(__name__)

def process_statement(pdf_path: str) -> ParsedStatement:
    """
    Main orchestration function to process a brokerage statement PDF.

    Pipeline:
    1. Extract text from PDF (using PyMuPDF)
    2. Detect broker from extracted text
    3. Select appropriate parser
    4. Parse text into structured data

    Args:
        pdf_path (str): Path to the PDF file.

    Returns:
        ParsedStatement: The parsed data object.

    Raises:
        ValueError: If file doesn't exist.
    """
    path = Path(pdf_path)
    if not path.exists():
        raise ValueError(f"File not found: {pdf_path}")

    logger.info(f"Processing: {path.name}")

    # 1. Extraction
    try:
        # Try table extraction first (graceful degradation)
        extracted_tables_map = extract_tables(path)

        # Text extraction (still needed for detection and fallback)
        # Use layout-aware extraction to cleaner columns if regex fallback is needed
        pages_text = extract_text_with_layout(path)
        full_text = "\n".join(pages_text.values())

        # 2. If no explicit tables found, try implicit detection
        if not any(extracted_tables_map.values()):
            logger.info("No explicit tables found, trying implicit column detection...")
            for page_num, text in pages_text.items():
                implicit_table = text_to_implicit_table(text)
                if implicit_table and len(implicit_table) > 2:  # Header + at least 2 data rows
                    logger.info(f"Detected implicit table on page {page_num} with {len(implicit_table)} rows")
                    extracted_tables_map[page_num] = [implicit_table]

        # Flatten tables for the parser: List of all tables across all pages
        # extracted_tables_map is Dict[int, List[List[List[str]]]]
        all_tables = []
        for page_num in sorted(extracted_tables_map.keys()):
            all_tables.extend(extracted_tables_map[page_num])

    except Exception as e:
        logger.error(f"Extraction failed: {e}")
        raise e

    # 2. Detection
    broker_name, confidence = detect_broker(full_text)
    logger.info(f"Detected Broker: {broker_name} (Confidence: {confidence:.2f})")

    # 3. Get Parser
    # Pass the flattened list of tables
    # Note: get_parser now returns GenericParser for unknown brokers if tables exist
    parser = get_parser(broker_name, full_text, tables=all_tables)
    if not parser:
        if broker_name == "unknown":
            logger.warning("Unknown broker and no tables available for generic parsing.")
            stmt = ParsedStatement(broker="Unknown")
            stmt.parse_errors.append("Could not detect broker and no usable tables found.")
        else:
            logger.error(f"No parser implementation found for: {broker_name}")
            stmt = ParsedStatement(broker=broker_name)
            stmt.parse_errors.append(f"No parser available for broker: {broker_name}")
        return stmt

    # 4. Parse
    try:
        logger.info(f"Parsing with {parser.__class__.__name__}...")
        statement = parser.parse()
        return statement
    except Exception as e:
        logger.error(f"Parsing error: {e}")
        stmt = ParsedStatement(broker=broker_name)
        stmt.parse_errors.append(f"Parsing exception: {str(e)}")
        return stmt
