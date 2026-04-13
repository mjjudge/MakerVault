"""Document storage service.

Handles saving uploaded files to the local document store volume,
computing SHA-256 checksums, and building relative storage paths.

All paths stored in the database are relative to ``document_store_path``
so the volume can be moved without breaking records.
"""

import hashlib
import os
import uuid
from pathlib import Path


def compute_sha256(data: bytes) -> str:
    """Return the hex-encoded SHA-256 digest of *data*."""
    return hashlib.sha256(data).hexdigest()


def build_storage_path(document_id: uuid.UUID, filename: str) -> str:
    """Return a relative storage path for a document file.

    Uses a two-level directory structure based on the first four hex characters
    of the UUID to keep directory sizes manageable:

        ``<aa>/<bb>/<document_id>_<filename>``

    The path is relative to the document store root.
    """
    hex_id = document_id.hex
    return os.path.join(hex_id[:2], hex_id[2:4], f"{document_id}_{filename}")


def save_document(
    store_root: str,
    document_id: uuid.UUID,
    filename: str,
    data: bytes,
) -> tuple[str, str, int]:
    """Write *data* to the document store and return metadata.

    Returns a tuple of ``(relative_path, checksum, file_size_bytes)``.

    The directory is created if it does not already exist.
    """
    relative_path = build_storage_path(document_id, filename)
    absolute_path = Path(store_root) / relative_path
    absolute_path.parent.mkdir(parents=True, exist_ok=True)
    absolute_path.write_bytes(data)
    checksum = compute_sha256(data)
    return relative_path, checksum, len(data)


def delete_document_file(store_root: str, relative_path: str) -> None:
    """Delete the stored file for a document, if it exists."""
    absolute_path = Path(store_root) / relative_path
    try:
        absolute_path.unlink(missing_ok=True)
    except OSError:
        pass


def get_absolute_path(store_root: str, relative_path: str) -> Path:
    """Return the absolute filesystem path for a stored document."""
    return Path(store_root) / relative_path
