from pathlib import Path
from typing import Optional
import logging
from brokerage_parser.extraction import extract_text
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
        pages_text = extract_text(path)
        # Combine first few pages for detection, or all for parsing
        # For simple parsing of single statement, combining all is fine for now
        # But detection usually only needs page 1
        full_text = "\n".join(pages_text.values())

        # We might want to pass page text map to parser later, but for now parser logic is string based
    except Exception as e:
        logger.error(f"Extraction failed: {e}")
        # Return a "failed" statement object or raise?
        # Requirement said "populate parse_errors list".
        # But we can't create ParsedStatement without broker/account info.
        # So we might define a fallback or re-raise.
        # Let's re-raise for severe extraction errors, assuming CLI handles it.
        raise e

    # 2. Detection
    broker_name, confidence = detect_broker(full_text)
    logger.info(f"Detected Broker: {broker_name} (Confidence: {confidence:.2f})")

    if broker_name == "unknown":
        logger.warning("Unknown broker. Parsing cannot proceed.")
        # Minimal empty statement
        stmt = ParsedStatement(broker="Unknown")
        stmt.parse_errors.append("Could not detect broker.")
        return stmt

    # 3. Get Parser
    parser = get_parser(broker_name, full_text)
    if not parser:
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
