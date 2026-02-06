import hashlib
from pathlib import Path
from typing import Any, Dict, Optional, Union, BinaryIO
from brokerage_parser.config import settings
from brokerage_parser.storage.base import StorageBackend

_backend: Optional[StorageBackend] = None

def get_backend() -> StorageBackend:
    global _backend
    if _backend:
        return _backend

    if settings.STORAGE_BACKEND == "s3":
        from brokerage_parser.storage.s3 import S3Storage
        _backend = S3Storage()
    else:
        from brokerage_parser.storage.local import LocalStorage
        _backend = LocalStorage()
    return _backend

def get_document_id(file_path: Path) -> str:
    """
    Generate a deterministic ID for a document based on its content (SHA-256).
    Kept for backward compatibility and ID generation.
    """
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        while True:
            chunk = f.read(8192)
            if not chunk:
                break
            sha256.update(chunk)
    return sha256.hexdigest()

def store_document(source: Union[Path, str, BinaryIO], doc_id: Optional[str] = None) -> str:
    """
    Store the document.
    Adapts legacy Path usage to backend file_obj usage.
    Returns the doc_id.
    """
    backend = get_backend()

    # Handle File Object (New Async Flow might use this if explicit)
    if hasattr(source, "read"):
        if not doc_id:
            raise ValueError("doc_id required when storing file object directly")
        # Ensure we are at start if it's a seekable stream?
        try:
            source.seek(0)
        except Exception:
            pass
        backend.store_document(source, f"{doc_id}.pdf")
        return doc_id

    # Handle Path (Legacy / Sync Flow)
    path = Path(source)
    if not doc_id:
        doc_id = get_document_id(path)

    with open(path, "rb") as f:
        backend.store_document(f, f"{doc_id}.pdf")

    return doc_id

def get_document_path(doc_id: str) -> Optional[Path]:
    """
    Legacy method. Only works if backend is local.
    S3 backend will assume doc_id is key and cannot return a local path without download.
    For legacy compatibility, if S3 is used, this might fail or we need to download to temp.
    Current usage in API: get_document_content uses this to return FileResponse.
    """
    backend = get_backend()
    if settings.STORAGE_BACKEND == "local":
        # Local backend implementation of get_document_url returns path string?
        # Actually local.get_document returns file obj.
        # We need to peek into backend or change API to use get_document stream.
        # For now, let's assume we fix API to use stream or this returns None for S3.
        base_dir = getattr(backend, "base_dir", None)
        if base_dir:
            p = base_dir / f"{doc_id}.pdf"
            if p.exists():
                return p
    return None

def get_document(doc_id: str) -> Optional[BinaryIO]:
    return get_backend().get_document(doc_id)

def get_document_url(doc_id: str) -> Optional[str]:
    return get_backend().get_document_url(f"documents/{doc_id}.pdf")

def store_report(doc_id: str, report_data: Dict[str, Any]) -> None:
    get_backend().store_report(f"documents/{doc_id}.pdf", report_data)

def get_report(doc_id: str) -> Optional[Dict[str, Any]]:
    # Try fetching assuming key pattern
    return get_backend().get_report(f"reports/{doc_id}.pdf.json")
