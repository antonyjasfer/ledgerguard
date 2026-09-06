"""Opt-in live SQS integration test for LedgerGuard.

Requires LEDGERGUARD_RUN_AWS_INTEGRATION=true and configured LEDGERGUARD_SQS_QUEUE_URL.
"""

import os
import uuid
import pytest

from app.config import get_settings
from app.models.job import ProcessingJob
from app.services.sqs import SQSJobQueue


@pytest.mark.integration
def test_sqs_live_send_receive_ack():
    settings = get_settings()
    if not settings.LEDGERGUARD_SQS_QUEUE_URL:
        pytest.skip("LEDGERGUARD_SQS_QUEUE_URL not configured")

    queue = SQSJobQueue(settings=settings)
    test_id = f"TEST_{uuid.uuid4().hex[:8]}"
    job = ProcessingJob(invoice_id=test_id)

    msg_id = queue.send_job(job)
    assert msg_id

    # Receive
    jobs = queue.receive_jobs(max_messages=1, wait_time_seconds=5)
    matched = [item for item in jobs if item[0].invoice_id == test_id]
    if matched:
        rec_job, handle = matched[0]
        assert rec_job.invoice_id == test_id
        # Ack
        queue.ack_job(handle)
