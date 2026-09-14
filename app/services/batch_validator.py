"""Batch validation and file sanitization service for LedgerGuard Phase 7.

Validates multi-document uploads, computes SHA-256 content digests, enforces size limits,
and generates safe S3 storage keys without trusting client-provided filenames.
"""

import hashlib
import os
import re
from pathlib import Path
from typing import NamedTuple

# Configurable limits for bulk ingestion
MAX_FILES_PER_BATCH: int = 100
MAX_BATCH_FILES: int = MAX_FILES_PER_BATCH
MAX_FILE_SIZE_BYTES: int = 10 * 1024 * 1024  # 10 MB per file
MAX_TOTAL_BATCH_SIZE_BYTES: int = 100 * 1024 * 1024  # 100 MB total batch
MAX_BATCH_SIZE_BYTES: int = MAX_TOTAL_BATCH_SIZE_BYTES

SUPPORTED_EXTENSIONS: set[str] = {".pdf", ".png", ".jpg", ".jpeg"}
SUPPORTED_MIME_TYPES: set[str] = {
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/jpg",
    "application/octet-stream",  # often sent by generic HTTP clients for PDFs
}


class FileValidationResult(NamedTuple):
    """Structured outcome of file validation check."""
    is_valid: bool
    error_code: str | None
    error_message: str | None
    safe_filename: str
    content_type: str
    file_size: int
    document_hash: str


def compute_sha256(data: bytes) -> str:
    """Compute deterministic SHA-256 hexadecimal digest of raw file content."""
    hasher = hashlib.sha256()
    hasher.update(data)
    return hasher.hexdigest()


def sanitize_filename(filename: str) -> str:
    """Sanitize incoming filename to strictly prevent path traversal and S3 key injection.

    1. Discards any directory path components (both UNIX / and Windows \\).
    2. Strips directory traversal sequences like '..'.
    3. Retains only alphanumeric characters, underscores, hyphens, and periods.
    4. Guarantees safe extension preservation.
    """
    if not filename or not filename.strip():
        return "document.pdf"

    # Extract base name from either POSIX or Windows path
    base = Path(filename.replace("\\", "/")).name
    base = base.replace("..", "").replace("/", "").replace("\\", "").replace("\x00", "")

    # Clean characters
    clean = re.sub(r"[^a-zA-Z0-9_.-]", "_", base)
    clean = clean.strip("._")

    if not clean:
        return "document.pdf"

    # Ensure a valid supported extension exists
    ext = Path(clean).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        clean = f"{clean}.pdf"

    return clean


sanitize_document_filename = sanitize_filename


def detect_mime_type(filename: str, provided_mime: str | None = None) -> str:
    """Determine normalized MIME content type based on extension and client hint."""
    ext = Path(filename).suffix.lower()
    if ext == ".pdf":
        return "application/pdf"
    if ext == ".png":
        return "image/png"
    if ext in (".jpg", ".jpeg"):
        return "image/jpeg"
    if provided_mime and provided_mime in SUPPORTED_MIME_TYPES:
        return provided_mime
    return "application/pdf"


def validate_single_file(
    filename: str,
    file_size: int,
    content_type: str | None = None,
) -> tuple[bool, str | None, str | None]:
    """Validate single file constraints (size and extension)."""
    if file_size == 0:
        return False, "EMPTY_FILE", f"File '{filename}' is empty (0 bytes)."
    if file_size > MAX_FILE_SIZE_BYTES:
        return (
            False,
            "FILE_TOO_LARGE",
            f"File '{filename}' size ({file_size} bytes) exceeds maximum limit ({MAX_FILE_SIZE_BYTES} bytes).",
        )
    ext = Path(filename).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        return (
            False,
            "UNSUPPORTED_EXTENSION",
            f"File extension '{ext}' is not supported. Supported extensions: {sorted(SUPPORTED_EXTENSIONS)}",
        )
    return True, None, None


def validate_batch_files(
    files: list[tuple[str, int, str | None]]
) -> tuple[bool, str | None, str | None]:
    """Validate aggregate batch constraints."""
    if len(files) > MAX_FILES_PER_BATCH:
        return (
            False,
            "BATCH_TOO_LARGE",
            f"Batch file count ({len(files)}) exceeds maximum limit of {MAX_FILES_PER_BATCH}.",
        )
    total_size = sum(sz for _, sz, _ in files)
    if total_size > MAX_TOTAL_BATCH_SIZE_BYTES:
        return (
            False,
            "BATCH_SIZE_EXCEEDED",
            f"Total batch size ({total_size} bytes) exceeds maximum limit of {MAX_TOTAL_BATCH_SIZE_BYTES} bytes.",
        )
    return True, None, None


def validate_batch_file(
    filename: str,
    data: bytes,
    provided_mime: str | None = None,
    max_file_size: int = MAX_FILE_SIZE_BYTES,
) -> FileValidationResult:
    """Validate a candidate file against enterprise batch ingestion constraints."""
    safe_name = sanitize_filename(filename)
    file_size = len(data)
    content_hash = compute_sha256(data)
    content_type = detect_mime_type(safe_name, provided_mime)

    is_valid, err_code, err_msg = validate_single_file(filename, file_size, content_type)
    if not is_valid:
        return FileValidationResult(
            is_valid=False,
            error_code=err_code,
            error_message=err_msg,
            safe_filename=safe_name,
            content_type=content_type,
            file_size=file_size,
            document_hash=content_hash,
        )

    return FileValidationResult(
        is_valid=True,
        error_code=None,
        error_message=None,
        safe_filename=safe_name,
        content_type=content_type,
        file_size=file_size,
        document_hash=content_hash,
    )


def generate_batch_document_s3_key(batch_id: str, document_id: str, safe_filename: str) -> str:
    """Generate canonical S3 object key for a batch document."""
    clean_batch = re.sub(r"[^a-zA-Z0-9_-]", "_", batch_id)
    clean_doc = re.sub(r"[^a-zA-Z0-9_-]", "_", document_id)
    clean_fn = sanitize_filename(safe_filename)
    return f"batches/{clean_batch}/documents/{clean_doc}/{clean_fn}"


generate_batch_key = generate_batch_document_s3_key
