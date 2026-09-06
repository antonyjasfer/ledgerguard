"""Opt-in live S3 integration test for LedgerGuard.

Requires LEDGERGUARD_RUN_AWS_INTEGRATION=true and configured LEDGERGUARD_S3_BUCKET.
"""

import os
import uuid
import pytest

from app.config import get_settings
from app.services.s3 import S3DocumentStore


@pytest.mark.integration
def test_s3_live_upload_download_delete():
    settings = get_settings()
    if not settings.LEDGERGUARD_S3_BUCKET:
        pytest.skip("LEDGERGUARD_S3_BUCKET not configured")

    store = S3DocumentStore(settings=settings)
    test_id = f"TEST_{uuid.uuid4().hex[:8]}"
    test_filename = "integration_test.pdf"
    test_data = b"%PDF-1.4 TEST CONTENT FOR INTEGRATION"

    key = store.upload_document(test_id, test_filename, test_data)
    try:
        assert store.document_exists(key) is True
        downloaded = store.download_document(key)
        assert downloaded == test_data
    finally:
        store.delete_document(key)
        assert store.document_exists(key) is False
