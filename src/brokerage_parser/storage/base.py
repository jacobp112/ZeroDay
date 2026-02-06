from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, BinaryIO
from pathlib import Path

class StorageBackend(ABC):
    @abstractmethod
    def store_document(self, file_obj: BinaryIO, filename: str, content_type: str = "application/pdf") -> str:
        """Store a document and return its unique identifier (or key)."""
        pass

    @abstractmethod
    def get_document(self, doc_id: str) -> Optional[BinaryIO]:
        """Retrieve a document file object."""
        pass

    @abstractmethod
    def get_document_url(self, doc_id: str, expiration: int = 3600) -> Optional[str]:
        """Get a temporary access URL (e.g. presigned S3 URL) or local path string."""
        pass

    @abstractmethod
    def store_report(self, doc_id: str, report_data: Dict[str, Any]) -> str:
        """Store the JSON report."""
        pass

    @abstractmethod
    def get_report(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve the JSON report."""
        pass
