import shutil
import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional, BinaryIO
from brokerage_parser.storage.base import StorageBackend

logger = logging.getLogger(__name__)

class LocalStorage(StorageBackend):
    def __init__(self, base_dir: str = "storage"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def store_document(self, file_obj: BinaryIO, filename: str, content_type: str = "application/pdf") -> str:
        # Generate ID or use filename. The filename logic in API creates a unique name.
        # If filename is distinct, we can use it.
        target_path = self.base_dir / filename
        with open(target_path, "wb") as f:
            shutil.copyfileobj(file_obj, f)

        logger.info(f"Stored local document at {target_path}")
        return str(target_path.absolute())

    def get_document(self, doc_id: str) -> Optional[BinaryIO]:
        path = Path(doc_id)
        if path.exists():
            return open(path, "rb")
        return None

    def get_document_url(self, doc_id: str, expiration: int = 3600) -> Optional[str]:
        # For local, we just return the path? Or None if specific URL logic needed.
        # This might not work for remote client access unless served via API.
        return str(doc_id)

    def store_report(self, doc_id: str, report_data: Dict[str, Any]) -> str:
        # doc_id here is assumed to be the path to the PDF or an ID
        # If it's a full path, derive report name
        path = Path(doc_id)
        report_path = path.parent / f"{path.stem}_report.json"

        with open(report_path, "w") as f:
            json.dump(report_data, f, indent=2, default=str)

        return str(report_path.absolute())

    def get_report(self, doc_id: str) -> Optional[Dict[str, Any]]:
        report_path = Path(doc_id)
        if report_path.exists():
            with open(report_path, "r") as f:
                return json.load(f)
        return None
