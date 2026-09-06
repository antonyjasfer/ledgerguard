"""Unit tests for background processing job models."""

import json

import pytest

from app.models.job import JobStatus, ProcessingJob


def test_job_initialization_defaults():
    """Verify default field values for a newly created ProcessingJob."""
    job = ProcessingJob(invoice_id="inv_12345")
    assert job.job_id.startswith("job_")
    assert job.invoice_id == "inv_12345"
    assert job.status == JobStatus.QUEUED
    assert job.attempt == 1
    assert job.processing_version == "1.0"
    assert job.s3_bucket is None
    assert job.s3_key is None


def test_job_sqs_message_serialization_roundtrip():
    """Verify serialization to and from SQS message body."""
    job = ProcessingJob(
        job_id="job_test_abc",
        invoice_id="inv_999",
        s3_bucket="my-invoice-bucket",
        s3_key="invoices/inv_999/bill.pdf",
        status=JobStatus.PROCESSING,
        attempt=2,
    )

    msg_body = job.to_sqs_message()
    parsed_json = json.loads(msg_body)
    assert parsed_json["job_id"] == "job_test_abc"
    assert parsed_json["invoice_id"] == "inv_999"
    assert parsed_json["s3_bucket"] == "my-invoice-bucket"
    assert parsed_json["s3_key"] == "invoices/inv_999/bill.pdf"
    assert parsed_json["status"] == "PROCESSING"
    assert parsed_json["attempt"] == 2

    # Roundtrip deserialization
    deserialized = ProcessingJob.from_sqs_message(msg_body)
    assert deserialized.job_id == job.job_id
    assert deserialized.invoice_id == job.invoice_id
    assert deserialized.s3_bucket == job.s3_bucket
    assert deserialized.s3_key == job.s3_key
    assert deserialized.status == JobStatus.PROCESSING
    assert deserialized.attempt == 2


def test_job_status_enum_values():
    """Verify all defined JobStatus enum values."""
    expected = {"QUEUED", "PROCESSING", "SUCCEEDED", "FAILED", "RETRYING"}
    actual = {s.value for s in JobStatus}
    assert expected == actual
