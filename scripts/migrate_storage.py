import os
import sys
import logging
from pathlib import Path

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), "../src"))

from brokerage_parser.config import settings
from brokerage_parser.storage.local import LocalStorage
from brokerage_parser.storage.s3 import S3Storage

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("migrate_storage")

def migrate():
    if settings.STORAGE_BACKEND != "s3":
        logger.error("Target backend must be S3. Please configure S3 settings.")
        return

    local_storage = LocalStorage()
    s3_storage = S3Storage()

    source_dir = local_storage.base_dir
    if not source_dir.exists():
        logger.info("No local storage directory found.")
        return

    files = list(source_dir.glob("*.pdf"))
    logger.info(f"Found {len(files)} documents to migrate.")

    for file_path in files:
        filename = file_path.name
        key = f"documents/{filename}"

        logger.info(f"Migrating {filename} -> {key}")
        try:
            with open(file_path, "rb") as f:
                s3_storage.store_document(f, filename)

            # Also check for report
            report_path = file_path.with_suffix(".pdf_report.json") # based on local implementation naming
            if not report_path.exists():
                report_path = source_dir / f"{file_path.stem}_report.json"

            if report_path.exists():
                logger.info(f"Migrating report {report_path.name}")
                with open(report_path, "r") as f:
                    import json
                    data = json.load(f)
                    s3_storage.store_report(key, data)

        except Exception as e:
            logger.error(f"Failed to migrate {filename}: {e}")

    logger.info("Migration complete.")

if __name__ == "__main__":
    migrate()
