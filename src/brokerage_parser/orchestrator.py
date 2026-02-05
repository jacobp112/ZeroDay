from pathlib import Path
from typing import Optional, List, Union
import logging
from brokerage_parser.extraction import extract_text, extract_tables, extract_text_with_layout, text_to_implicit_table, extract_rich_text, RichTable
from brokerage_parser.detection import detect_broker
from brokerage_parser.parsers import get_parser
from brokerage_parser.models import ParsedStatement, TaxWrapper

logger = logging.getLogger(__name__)

def process_statement(pdf_path: str, include_sources: bool = False) -> ParsedStatement:
    """
    Main orchestration function to process a brokerage statement PDF.

    Steps:
    1. Extract text and tables (including source lineage if requested)
    2. Detect broker
    3. Initialize specific parser
    4. Parse and return result

    Args:
        pdf_path (str): Path to the PDF file.
        include_sources (bool): If True, extract rich text with bounding box information line.

    Returns:
        ParsedStatement: The parsed data object.
    """
    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {pdf_path}")

    logger.info(f"Processing: {path.name}")

    # 1. Extract Text
    # Use layout-preserving text for main parsing text
    pages_text = extract_text_with_layout(path)
    full_text = "\n".join(pages_text.values())

    # 2. Extract Tables
    # extract_tables now returns RichTable objects (with bboxes)
    # We flatten them for the parser
    extracted_tables_map = extract_tables(path)
    rich_tables_flat = []
    plain_tables_flat = []

    for page_tables in extracted_tables_map.values():
        for table in page_tables:
            rich_tables_flat.append(table)
            plain_tables_flat.append(table.to_plain())

    # 3. Extract Rich Text (if requested)
    rich_text_map = {}
    if include_sources:
        logger.info(f"Extracting rich text for source tracking from {path.name}")
        rich_text_map = extract_rich_text(path)

    # 4. Detect Broker
    broker_name, confidence = detect_broker(full_text)
    logger.info(f"Detected Broker: {broker_name} (Confidence: {confidence})")

    # 5. Get Parser Class
    parser_class = get_parser(broker_name)
    if not parser_class:
        # Handle unknown/generic?
        # If get_parser returns None, we might raise or use a default.
        # Assuming get_parser handles defaults or we raise.
        raise ValueError(f"No parser found for broker: {broker_name}")

    # 6. Instantiate Parser
    # We pass both plain tables (for backward compat logic) and rich_tables (for source tracking)
    # We need to ensure Parser.__init__ accepts rich_tables. We will update base.py next.
    parser = parser_class(
        text=full_text,
        tables=plain_tables_flat,
        rich_text_map=rich_text_map,
        # We'll need to update Parser signature to accept this, or pass it via kwargs if usage is dynamic.
        # Ideally explicit.
        # For now, let's assume we update base.py to accept it.
        rich_tables=rich_tables_flat
    )

    # 7. Parse
    logger.info(f"Parsing with {parser.__class__.__name__}...")
    statement = parser.parse()

    # Optional: logic to run validation?
    # statement.validate()

    return statement
