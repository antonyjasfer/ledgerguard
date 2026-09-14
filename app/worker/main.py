"""Background worker process entrypoint for LedgerGuard.

Polls the SQS job queue continuously with bounded concurrency (MAX_WORKER_CONCURRENCY),
applies worker backpressure, dispatches jobs to a ThreadPoolExecutor,
and handles graceful shutdown.
"""

from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
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
            auto_extract=True,
        )
        self.executor = ThreadPoolExecutor(
            max_workers=self.settings.MAX_WORKER_CONCURRENCY,
            thread_name_prefix="lg-worker",
        )
        self.active_futures: set[Future] = set()
        self.is_running = True

    def stop(self, *args):
        logger.info("Shutdown signal received. Waiting for in-flight jobs to complete...")
        self.is_running = False

    def _safe_process(self, job, receipt_handle):
        """Execute processing with unhandled exception protection."""
        try:
            return self.processor.process_job(job, receipt_handle=receipt_handle)
        except Exception as exc:
            logger.exception("Unexpected fatal error processing job %s: %s", job.job_id, exc)
            return False

    def run(self, max_iterations: int | None = None):
        logger.info(
            "LedgerGuard background worker starting (concurrency=%d, prefetch=%d)...",
            self.settings.MAX_WORKER_CONCURRENCY,
            self.settings.BATCH_PREFETCH_SIZE,
        )
        iterations = 0

        while self.is_running:
            if max_iterations is not None and iterations >= max_iterations:
                break
            iterations += 1

            try:
                # 1. Prune finished futures
                self.active_futures = {f for f in self.active_futures if not f.done()}

                # 2. Worker Backpressure Check
                # If in-flight jobs reach pool capacity, wait for at least one to finish before polling SQS
                if len(self.active_futures) >= self.settings.MAX_WORKER_CONCURRENCY:
                    done, _ = wait(
                        self.active_futures,
                        return_when=FIRST_COMPLETED,
                        timeout=0.5,
                    )
                    self.active_futures -= done
                    continue

                # 3. Calculate dynamic prefetch window based on free capacity
                free_slots = self.settings.MAX_WORKER_CONCURRENCY - len(self.active_futures)
                prefetch = max(1, min(self.settings.BATCH_PREFETCH_SIZE, free_slots, 10))

                jobs = self.job_queue.receive_jobs(
                    max_messages=prefetch,
                    wait_time_seconds=5,
                )
                if not jobs:
                    continue

                # 4. Dispatch received jobs to worker thread pool
                for job, receipt_handle in jobs:
                    if not self.is_running:
                        break
                    future = self.executor.submit(self._safe_process, job, receipt_handle)
                    self.active_futures.add(future)

            except Exception as exc:
                logger.error("Error in worker polling loop: %s", exc)
                time.sleep(2)

        # Graceful shutdown: wait for remaining in-flight futures
        logger.info("Draining %d active in-flight worker jobs...", len(self.active_futures))
        self.executor.shutdown(wait=True)
        logger.info("LedgerGuard background worker stopped cleanly.")


def main():
    service = WorkerService()
    signal.signal(signal.SIGINT, service.stop)
    signal.signal(signal.SIGTERM, service.stop)
    service.run()


if __name__ == "__main__":
    main()
