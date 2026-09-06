"""Background worker process entrypoint for LedgerGuard.

Polls the SQS job queue continuously, dispatches jobs to InvoiceProcessor,
and handles graceful shutdown.
"""

import logging
import signal
import sys
import time

from app.config import get_settings
from app.services.dynamodb import DynamoDBInvoiceRepository
from app.services.s3 import S3DocumentStore
from app.services.secrets import SecretsManagerProvider
from app.services.sqs import SQSJobQueue
from app.worker.processor import InvoiceProcessor

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("ledgerguard.worker")


class WorkerService:
    """Lifecycle manager for the background worker polling loop."""

    def __init__(self):
        self.settings = get_settings()
        self.document_store = S3DocumentStore(settings=self.settings)
        self.repository = DynamoDBInvoiceRepository(settings=self.settings)
        self.job_queue = SQSJobQueue(settings=self.settings)
        self.secret_provider = SecretsManagerProvider(settings=self.settings)
        self.processor = InvoiceProcessor(
            document_store=self.document_store,
            repository=self.repository,
            job_queue=self.job_queue,
            secret_provider=self.secret_provider,
            settings=self.settings,
        )
        self.is_running = True

    def stop(self, *args):
        logger.info("Shutdown signal received. Finishing active jobs...")
        self.is_running = False

    def run(self, max_iterations: int | None = None):
        logger.info("LedgerGuard background worker starting...")
        iterations = 0

        while self.is_running:
            if max_iterations is not None and iterations >= max_iterations:
                break
            iterations += 1

            try:
                jobs = self.job_queue.receive_jobs(
                    max_messages=5,
                    wait_time_seconds=10,
                )
                if not jobs:
                    continue

                for job, receipt_handle in jobs:
                    if not self.is_running:
                        break
                    try:
                        self.processor.process_job(job, receipt_handle=receipt_handle)
                    except Exception as exc:
                        logger.exception("Unexpected error processing job %s: %s", job.job_id, exc)

            except Exception as exc:
                logger.error("Error in worker polling loop: %s", exc)
                time.sleep(2)

        logger.info("LedgerGuard background worker stopped.")


def main():
    service = WorkerService()
    signal.signal(signal.SIGINT, service.stop)
    signal.signal(signal.SIGTERM, service.stop)
    service.run()


if __name__ == "__main__":
    main()
