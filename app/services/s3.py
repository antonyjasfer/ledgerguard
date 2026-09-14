"""Amazon S3 Document Store implementation for LedgerGuard.

Handles document upload, retrieval, and deletion with strict key sanitization
to prevent path traversal and unexpected object overwrites.
"""

import os
import re
from pathlib import Path
from typing import Any

import boto3
from botocore.exceptions import ClientError

from app.config import Settings, get_settings
from app.services.interfaces import DocumentStore


def sanitize_filename(filename: str) -> str:
    """Sanitize input filename to prevent path traversal and invalid S3 key characters.

    1. Extracts pure filename, discarding directory paths.
    2. Strips leading dots (e.g. '..') and unsafe symbols.
    3. Retains only alphanumeric, hyphen, underscore, and dot characters.
    """
    base_name = Path(filename).name
    # Strip any directory traversal remnants
    base_name = base_name.replace("..", "").replace("/", "").replace("\\", "")
    # Allow alphanumeric, underscore, dash, dot
    sanitized = re.sub(r"[^a-zA-Z0-9_.-]", "_", base_name)
    # Strip leading/trailing dots or underscores
    sanitized = sanitized.strip("._")
    if not sanitized:
        return "document.pdf"
    return sanitized


def sanitize_id(identifier: str) -> str:
    """Sanitize identifier used in S3 path segments."""
    cleaned = re.sub(r"[^a-zA-Z0-9_-]", "_", identifier).strip("_")
    return cleaned or "default"


_UNSET = object()


class S3DocumentStore(DocumentStore):
    """Document store backed by Amazon S3."""

    def __init__(
        self,
        bucket_name: Any = _UNSET,
        region_name: str | None = None,
        profile_name: str | None = None,
        s3_client: Any = None,
        settings: Settings | None = None,
    ):
        resolved_settings = settings or get_settings()
        self.bucket_name = (
            resolved_settings.LEDGERGUARD_S3_BUCKET
            if bucket_name is _UNSET
            else bucket_name
        )
        self.region_name = region_name or resolved_settings.AWS_REGION
        self.profile_name = profile_name if profile_name is not None else resolved_settings.AWS_PROFILE

        if s3_client is not None:
            self._client = s3_client
        else:
            session_kwargs: dict[str, Any] = {"region_name": self.region_name}
            if self.profile_name:
                session_kwargs["profile_name"] = self.profile_name
            session = boto3.Session(**session_kwargs)
            self._client = session.client("s3")

    def _ensure_bucket(self) -> str:
        if not self.bucket_name:
            raise ValueError(
                "S3 bucket name is not configured. Set LEDGERGUARD_S3_BUCKET environment variable."
            )
        return self.bucket_name

    def generate_key(self, invoice_id: str, filename: str) -> str:
        """Generate a sanitized, traversal-safe object key: invoices/{invoice_id}/{filename}."""
        safe_inv_id = sanitize_id(invoice_id)
        safe_fname = sanitize_filename(filename)
        return f"invoices/{safe_inv_id}/{safe_fname}"

    def upload_document(
        self,
        invoice_id: str,
        filename: str,
        data: bytes,
        content_type: str = "application/pdf",
    ) -> str:
        """Upload raw document bytes to S3 using a sanitized key."""
        bucket = self._ensure_bucket()
        key = self.generate_key(invoice_id, filename)
        self._client.put_object(
            Bucket=bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
        )
        return key

    def upload_batch_document(
        self,
        batch_id: str,
        document_id: str,
        filename: str,
        data: bytes,
        content_type: str = "application/pdf",
    ) -> str:
        """Upload a raw batch invoice document to S3: batches/{batch_id}/documents/{document_id}/{filename}."""
        bucket = self._ensure_bucket()
        from app.services.batch_validator import generate_batch_key
        key = generate_batch_key(batch_id, document_id, filename)
        self._client.put_object(
            Bucket=bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
        )
        return key

    def download_document(self, key: str) -> bytes:
        """Download document content bytes by storage key."""
        bucket = self._ensure_bucket()
        try:
            response = self._client.get_object(Bucket=bucket, Key=key)
            return response["Body"].read()
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code")
            if code in ("NoSuchKey", "404"):
                raise FileNotFoundError(f"Document key '{key}' not found in bucket '{bucket}'") from exc
            raise

    def document_exists(self, key: str) -> bool:
        """Check if an object exists in the S3 bucket using head_object."""
        bucket = self._ensure_bucket()
        try:
            self._client.head_object(Bucket=bucket, Key=key)
            return True
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code")
            if code in ("NoSuchKey", "404", "NotFound"):
                return False
            raise

    def delete_document(self, key: str) -> bool:
        """Delete an object from the S3 bucket if explicitly requested."""
        bucket = self._ensure_bucket()
        try:
            self._client.delete_object(Bucket=bucket, Key=key)
            return True
        except ClientError:
            return False
