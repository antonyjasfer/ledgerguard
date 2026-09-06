"""Unit tests for SQS JobQueue implementation."""

from unittest.mock import MagicMock

import pytest

from app.models.job import JobStatus, ProcessingJob
from app.services.sqs import SQSJobQueue


def test_send_job_success():
    """Publishing job sends serialized payload to SQS queue URL."""
    mock_client = MagicMock()
    mock_client.send_message.return_value = {"MessageId": "msg_abc123"}
    queue = SQSJobQueue(
        queue_url="https://sqs.us-east-1.amazonaws.com/123/ledgerguard-jobs",
        sqs_client=mock_client,
    )

    job = ProcessingJob(invoice_id="inv_555")
    msg_id = queue.send_job(job)

    assert msg_id == "msg_abc123"
    mock_client.send_message.assert_called_once()
    call_kwargs = mock_client.send_message.call_args[1]
    assert call_kwargs["QueueUrl"] == "https://sqs.us-east-1.amazonaws.com/123/ledgerguard-jobs"
    assert "inv_555" in call_kwargs["MessageBody"]


def test_receive_jobs_success():
    """Receiving jobs extracts payload and receipt handles."""
    mock_client = MagicMock()
    mock_job = ProcessingJob(job_id="job_777", invoice_id="inv_777")
    mock_client.receive_message.return_value = {
        "Messages": [
            {
                "MessageId": "msg_1",
                "ReceiptHandle": "receipt_1",
                "Body": mock_job.to_sqs_message(),
                "Attributes": {"ApproximateReceiveCount": "2"},
            }
        ]
    }
    queue = SQSJobQueue(
        queue_url="https://sqs.us-east-1.amazonaws.com/123/test-queue",
        sqs_client=mock_client,
    )

    jobs = queue.receive_jobs(max_messages=1)
    assert len(jobs) == 1
    job, handle = jobs[0]
    assert job.job_id == "job_777"
    assert job.invoice_id == "inv_777"
    assert job.attempt == 2
    assert handle == "receipt_1"


def test_receive_jobs_empty():
    """Empty queue returns empty list."""
    mock_client = MagicMock()
    mock_client.receive_message.return_value = {}
    queue = SQSJobQueue(
        queue_url="https://sqs.us-east-1.amazonaws.com/123/test-queue",
        sqs_client=mock_client,
    )

    jobs = queue.receive_jobs()
    assert jobs == []


def test_receive_malformed_message_raises():
    """Malformed JSON body raises ValueError."""
    mock_client = MagicMock()
    mock_client.receive_message.return_value = {
        "Messages": [
            {
                "MessageId": "bad_msg",
                "ReceiptHandle": "bad_handle",
                "Body": "INVALID_JSON{{",
                "Attributes": {},
            }
        ]
    }
    queue = SQSJobQueue(
        queue_url="https://sqs.us-east-1.amazonaws.com/123/test-queue",
        sqs_client=mock_client,
    )

    with pytest.raises(ValueError, match="Malformed SQS message body"):
        queue.receive_jobs()


def test_ack_job():
    """Acknowledging job calls delete_message on queue."""
    mock_client = MagicMock()
    queue = SQSJobQueue(
        queue_url="https://sqs.us-east-1.amazonaws.com/123/test-queue",
        sqs_client=mock_client,
    )

    queue.ack_job("receipt_xyz")
    mock_client.delete_message.assert_called_once_with(
        QueueUrl="https://sqs.us-east-1.amazonaws.com/123/test-queue",
        ReceiptHandle="receipt_xyz",
    )


def test_nack_job():
    """Nacking job changes visibility timeout to 0 for immediate retry."""
    mock_client = MagicMock()
    queue = SQSJobQueue(
        queue_url="https://sqs.us-east-1.amazonaws.com/123/test-queue",
        sqs_client=mock_client,
    )

    queue.nack_job("receipt_xyz", visibility_timeout=0)
    mock_client.change_message_visibility.assert_called_once_with(
        QueueUrl="https://sqs.us-east-1.amazonaws.com/123/test-queue",
        ReceiptHandle="receipt_xyz",
        VisibilityTimeout=0,
    )


def test_missing_queue_url_raises():
    """Operations without configured queue URL raise ValueError."""
    queue = SQSJobQueue(queue_url=None, sqs_client=MagicMock())
    with pytest.raises(ValueError, match="SQS queue URL is not configured"):
        queue.send_job(ProcessingJob(invoice_id="inv_1"))
