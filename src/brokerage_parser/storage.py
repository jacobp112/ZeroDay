import hashlib
import shutil
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Default storage location (can be made configurable via environment variable)
STORAGE_DIR = Path("storage")

def get_document_id(file_path: Path) -> str:
    """
    Generate a deterministic ID for a document based on its content (SHA-256).
    """
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        while True:
            chunk = f.read(8192)
            if not chunk:
                break
            sha256.update(chunk)
    return sha256.hexdigest()

def store_document(source_path: Path, doc_id: Optional[str] = None) -> str:
    """
    Store the document in the persistent storage directory.

    Args:
        source_path: Path to the source file (e.g., temp upload).
        doc_id: Optional pre-calculated ID. If None, calculates it.

    Returns:
        The document ID (hash).
    """
    if not doc_id:
        doc_id = get_document_id(source_path)

    if not STORAGE_DIR.exists():
        STORAGE_DIR.mkdir(parents=True, exist_ok=True)

    target_path = STORAGE_DIR / f"{doc_id}.pdf"

    if not target_path.exists():
        shutil.copy2(source_path, target_path)
        logger.info(f"Stored document {doc_id} at {target_path}")
    else:
        logger.debug(f"Document {doc_id} already exists.")

    return doc_id

def get_document_path(doc_id: str) -> Optional[Path]:
    """Get the path to a stored document by its ID."""
    target_path = STORAGE_DIR / f"{doc_id}.pdf"
    if target_path.exists():
        return target_path
    return None

def store_report(doc_id: str, report_data: dict) -> None:
    """Store the parsed report JSON associated with a document ID."""
    import json
    if not STORAGE_DIR.exists():
        STORAGE_DIR.mkdir(parents=True, exist_ok=True)

    report_path = STORAGE_DIR / f"{doc_id}_report.json"
    with open(report_path, "w") as f:
        json.dump(report_data, f, indent=2, default=str)
    logger.info(f"Stored report for {doc_id} at {report_path}")

def get_report(doc_id: str) -> Optional[dict]:
    """Retrieve the stored report JSON for a document ID."""
    import json
    report_path = STORAGE_DIR / f"{doc_id}_report.json"
    if report_path.exists():
        with open(report_path, "r") as f:
            return json.load(f)
    return None
