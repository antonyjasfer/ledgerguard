"""Unit tests for Amazon S3 DocumentStore implementation."""

from io import BytesIO
from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError

from app.config import Settings
from app.services.s3 import S3DocumentStore, sanitize_filename, sanitize_id


def test_sanitize_filename_traversal():
    """Path traversal elements must be completely stripped from filenames."""
    assert sanitize_filename("../../etc/passwd") == "passwd"
    assert sanitize_filename("..\\..\\secret.txt") == "secret.txt"
    assert sanitize_filename("/var/log/audit.log") == "audit.log"
    assert sanitize_filename("C:\\Users\\Admin\\invoice.pdf") == "invoice.pdf"


def test_sanitize_filename_characters():
    """Unsafe and whitespace characters must be sanitized safely."""
    cleaned = sanitize_filename("Invoice #445 (Draft) [Final].pdf")
    assert " " not in cleaned
    assert "#" not in cleaned
    assert "(" not in cleaned
    assert "[" not in cleaned
    assert cleaned.endswith(".pdf")


def test_sanitize_filename_empty():
    """Empty or symbol-only filenames should fallback to document.pdf."""
    assert sanitize_filename("") == "document.pdf"
    assert sanitize_filename("...") == "document.pdf"


def test_generate_key():
    """Verify generated keys follow standard hierarchical pattern."""
    mock_client = MagicMock()
    store = S3DocumentStore(bucket_name="test-bucket", s3_client=mock_client)
    key = store.generate_key("inv_12345", "../../my_bill.pdf")
    assert key == "invoices/inv_12345/my_bill.pdf"


def test_upload_document_success():
    """Uploading document issues put_object with correct arguments."""
    mock_client = MagicMock()
    store = S3DocumentStore(bucket_name="test-bucket", s3_client=mock_client)

    key = store.upload_document(
        invoice_id="inv_101",
        filename="vendor_bill.pdf",
        data=b"%PDF-1.4 test invoice content",
    )

    assert key == "invoices/inv_101/vendor_bill.pdf"
    mock_client.put_object.assert_called_once_with(
        Bucket="test-bucket",
        Key="invoices/inv_101/vendor_bill.pdf",
        Body=b"%PDF-1.4 test invoice content",
        ContentType="application/pdf",
    )


def test_download_document_success():
    """Downloading document returns content bytes."""
    mock_client = MagicMock()
    mock_client.get_object.return_value = {
        "Body": BytesIO(b"fake pdf content")
    }
    store = S3DocumentStore(bucket_name="test-bucket", s3_client=mock_client)

    data = store.download_document("invoices/inv_101/test.pdf")
    assert data == b"fake pdf content"


def test_download_document_not_found():
    """Missing S3 document raises FileNotFoundError."""
    mock_client = MagicMock()
    error_response = {"Error": {"Code": "NoSuchKey", "Message": "Key not found"}}
    mock_client.get_object.side_effect = ClientError(error_response, "GetObject")

    store = S3DocumentStore(bucket_name="test-bucket", s3_client=mock_client)
    with pytest.raises(FileNotFoundError):
        store.download_document("invoices/missing.pdf")


def test_document_exists():
    """Checking existence correctly interprets head_object responses."""
    mock_client = MagicMock()
    store = S3DocumentStore(bucket_name="test-bucket", s3_client=mock_client)

    # Exists
    mock_client.head_object.return_value = {}
    assert store.document_exists("invoices/exists.pdf") is True

    # Not found
    error_response = {"Error": {"Code": "404", "Message": "Not Found"}}
    mock_client.head_object.side_effect = ClientError(error_response, "HeadObject")
    assert store.document_exists("invoices/notfound.pdf") is False


def test_delete_document():
    """Deleting document invokes delete_object."""
    mock_client = MagicMock()
    store = S3DocumentStore(bucket_name="test-bucket", s3_client=mock_client)

    res = store.delete_document("invoices/to_delete.pdf")
    assert res is True
    mock_client.delete_object.assert_called_once_with(
        Bucket="test-bucket",
        Key="invoices/to_delete.pdf",
    )


def test_missing_bucket_raises_value_error():
    """Attempting operations with unconfigured bucket raises ValueError."""
    store = S3DocumentStore(bucket_name=None, s3_client=MagicMock())
    with pytest.raises(ValueError, match="S3 bucket name is not configured"):
        store.upload_document("inv_1", "doc.pdf", b"data")
