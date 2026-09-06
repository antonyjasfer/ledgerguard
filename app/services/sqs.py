"""Amazon SQS Job Queue implementation for LedgerGuard.

Handles background job publishing, receiving with visibility timeout management,
and explicit message acknowledgment.
"""

from typing import Any

import boto3
from botocore.exceptions import ClientError

from app.config import Settings, get_settings
from app.models.job import ProcessingJob
from app.services.interfaces import JobQueue


class SQSJobQueue(JobQueue):
    """Background job queue backed by Amazon SQS."""

    def __init__(
        self,
        queue_url: str | None = None,
        region_name: str | None = None,
        profile_name: str | None = None,
        sqs_client: Any = None,
        visibility_timeout: int | None = None,
        max_attempts: int | None = None,
        settings: Settings | None = None,
    ):
        resolved_settings = settings or get_settings()
        self.queue_url = queue_url or resolved_settings.LEDGERGUARD_SQS_QUEUE_URL
        self.region_name = region_name or resolved_settings.AWS_REGION
        self.profile_name = profile_name if profile_name is not None else resolved_settings.AWS_PROFILE
        self.visibility_timeout = visibility_timeout or resolved_settings.SQS_VISIBILITY_TIMEOUT
        self.max_attempts = max_attempts or resolved_settings.SQS_MAX_ATTEMPTS

        if sqs_client is not None:
            self._client = sqs_client
        else:
            session_kwargs: dict[str, Any] = {"region_name": self.region_name}
            if self.profile_name:
                session_kwargs["profile_name"] = self.profile_name
            session = boto3.Session(**session_kwargs)
            self._client = session.client("sqs")

    def _ensure_queue_url(self) -> str:
        if not self.queue_url:
            raise ValueError(
                "SQS queue URL is not configured. Set LEDGERGUARD_SQS_QUEUE_URL environment variable."
            )
        return self.queue_url

    def send_job(self, job: ProcessingJob) -> str:
        """Publish a serialized ProcessingJob to SQS and return message identifier."""
        queue_url = self._ensure_queue_url()
        body = job.to_sqs_message()
        response = self._client.send_message(
            QueueUrl=queue_url,
            MessageBody=body,
        )
        return response.get("MessageId", "")

    def receive_jobs(
        self,
        max_messages: int = 1,
        wait_time_seconds: int = 10,
        visibility_timeout: int | None = None,
    ) -> list[tuple[ProcessingJob, str]]:
        """Poll queue for jobs, returning parsed (ProcessingJob, receipt_handle) pairs."""
        queue_url = self._ensure_queue_url()
        timeout = visibility_timeout if visibility_timeout is not None else self.visibility_timeout

        response = self._client.receive_message(
            QueueUrl=queue_url,
            MaxNumberOfMessages=min(max_messages, 10),
            WaitTimeSeconds=wait_time_seconds,
            VisibilityTimeout=timeout,
            AttributeNames=["ApproximateReceiveCount"],
        )

        messages = response.get("Messages", [])
        jobs: list[tuple[ProcessingJob, str]] = []

        for msg in messages:
            receipt_handle = msg.get("ReceiptHandle", "")
            body = msg.get("Body", "{}")
            attributes = msg.get("Attributes", {})
            receive_count = int(attributes.get("ApproximateReceiveCount", 1))

            try:
                job = ProcessingJob.from_sqs_message(body)
                job.attempt = receive_count
                jobs.append((job, receipt_handle))
            except Exception as exc:
                # Malformed message handling: record or nack
                raise ValueError(f"Malformed SQS message body in {msg.get('MessageId')}: {exc}") from exc

        return jobs

    def ack_job(self, receipt_handle: str) -> None:
        """Delete message from SQS upon successful processing and persistence."""
        queue_url = self._ensure_queue_url()
        self._client.delete_message(
            QueueUrl=queue_url,
            ReceiptHandle=receipt_handle,
        )

    def nack_job(self, receipt_handle: str, visibility_timeout: int = 0) -> None:
        """Reset message visibility timeout to make it immediately available for retry."""
        queue_url = self._ensure_queue_url()
        self._client.change_message_visibility(
            QueueUrl=queue_url,
            ReceiptHandle=receipt_handle,
            VisibilityTimeout=visibility_timeout,
        )
