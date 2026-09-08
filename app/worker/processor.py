"""Background worker processor executing the LedgerGuard invoice verification pipeline.

Coordinates SQS job polling, S3 document presence verification, deterministic
tool orchestration, Decision Guard enforcement, and durable DynamoDB state updates.

Strictly enforces transactional ordering:
State & Decision Persisted -> SQS Message Acknowledged.
Logs ONLY safe operational metadata, never credentials, raw PDFs, or payloads.
"""

import logging
from datetime import datetime, timezone
from typing import Sequence

from app.agent.orchestrator import run_verification_workflow
from app.config import Settings, get_settings
from app.models.audit import AuditEvent, AuditEventType
from app.models.decision import AgentDecision, VerificationDecision
from app.models.invoice import Invoice
from app.models.job import JobStatus, ProcessingJob
from app.models.persistence import InvoiceRecord
from app.models.policy import PolicyConfig
from app.services.interfaces import DocumentStore, InvoiceRepository, JobQueue, SecretProvider
from app.services.state import ProcessingState

logger = logging.getLogger("ledgerguard.worker")


def decision_to_state(decision: AgentDecision) -> ProcessingState:
    """Map final AgentDecision to internal ProcessingState."""
    if decision == AgentDecision.AUTO_APPROVE:
        return ProcessingState.AUTO_APPROVED
    if decision == AgentDecision.MANUAL_REVIEW:
        return ProcessingState.MANUAL_REVIEW
    if decision == AgentDecision.BLOCK:
        return ProcessingState.BLOCKED
    if decision == AgentDecision.ESCALATE:
        return ProcessingState.MANUAL_REVIEW
    return ProcessingState.VERIFIED


class InvoiceProcessor:
    """Core processor orchestrating invoice verification jobs."""

    def __init__(
        self,
        document_store: DocumentStore,
        repository: InvoiceRepository,
        job_queue: JobQueue,
        secret_provider: SecretProvider | None = None,
        settings: Settings | None = None,
    ):
        self.document_store = document_store
        self.repository = repository
        self.job_queue = job_queue
        self.secret_provider = secret_provider
        self.settings = settings or get_settings()

    def process_job(
        self,
        job: ProcessingJob,
        receipt_handle: str | None = None,
        invoice_data: Invoice | None = None,
        history: Sequence[Invoice] = (),
        policy_config: PolicyConfig | None = None,
    ) -> bool:
        """Process a single invoice verification job end-to-end.

        Returns:
            True if successfully processed (or safely deduplicated),
            False if processing encountered an unrecoverable or retryable error.
        """
        job_id = job.job_id
        invoice_id = job.invoice_id

        logger.info(
            "Worker received job. job_id=%s, invoice_id=%s, attempt=%d",
            job_id,
            invoice_id,
            job.attempt,
        )

        # 1. Validation of Job Payload
        if not job_id or not invoice_id:
            logger.error("Rejecting invalid job missing job_id or invoice_id.")
            return False

        # 2. Idempotency Check
        if self.repository.is_already_processed(invoice_id):
            logger.info(
                "[IDEMPOTENCY] Invoice '%s' has already reached terminal state. Skipping duplicate execution for job '%s'.",
                invoice_id,
                job_id,
            )
            # Record audit event marking duplicate detection
            self.repository.save_audit_event(
                AuditEvent(
                    invoice_id=invoice_id,
                    job_id=job_id,
                    event_type=AuditEventType.PROCESSING_COMPLETED,
                    details={"status": "already_processed", "job_id": job_id},
                )
            )
            # Acknowledge message so it does not loop
            if receipt_handle:
                self.job_queue.ack_job(receipt_handle)
            return True

        # 3. Transition to PROCESSING state
        now_iso = datetime.now(timezone.utc).isoformat()
        self.repository.save_audit_event(
            AuditEvent(
                invoice_id=invoice_id,
                job_id=job_id,
                event_type=AuditEventType.PROCESSING_STARTED,
                details={"attempt": job.attempt, "s3_key": job.s3_key},
            )
        )

        try:
            existing_record = self.repository.get_record(invoice_id)
            if existing_record is None and invoice_data is not None:
                # First time record creation
                initial_record = InvoiceRecord.from_invoice(
                    invoice=invoice_data,
                    document_s3_key=job.s3_key,
                    status=ProcessingState.PROCESSING,
                    idempotency_key=job_id,
                )
                self.repository.save_record(initial_record)
            else:
                self.repository.update_status(
                    invoice_id=invoice_id,
                    status=ProcessingState.PROCESSING,
                    updated_at=now_iso,
                )
        except Exception as exc:
            logger.exception(
                "Failed to initialize processing state in repository. job_id=%s, invoice_id=%s",
                job_id,
                invoice_id,
            )
            return False

        # 4. Source document presence check (if S3 key provided)
        if job.s3_key:
            if not self.document_store.document_exists(job.s3_key):
                logger.error(
                    "Missing S3 document artifact. job_id=%s, invoice_id=%s, key=%s",
                    job_id,
                    invoice_id,
                    job.s3_key,
                )
                self.repository.update_status(
                    invoice_id=invoice_id,
                    status=ProcessingState.FAILED,
                    updated_at=datetime.now(timezone.utc).isoformat(),
                )
                self.repository.save_audit_event(
                    AuditEvent(
                        invoice_id=invoice_id,
                        job_id=job_id,
                        event_type=AuditEventType.PROCESSING_FAILED,
                        details={"error_category": "MISSING_S3_DOCUMENT", "key": job.s3_key},
                    )
                )
                # DO NOT ACK message - visibility timeout will handle retry or DLQ
                return False

            self.repository.save_audit_event(
                AuditEvent(
                    invoice_id=invoice_id,
                    job_id=job_id,
                    event_type=AuditEventType.DOCUMENT_RECEIVED,
                    details={"s3_bucket": job.s3_bucket, "s3_key": job.s3_key},
                )
            )

        # 5. Resolve Invoice Data
        resolved_invoice = invoice_data
        if resolved_invoice is None and existing_record is not None:
            try:
                resolved_invoice = existing_record.to_invoice()
            except Exception as exc:
                logger.warning("Could not reconstruct Invoice from existing record %s: %s", invoice_id, exc)
        if resolved_invoice is None:
            logger.error(
                "No invoice data available for processing. job_id=%s, invoice_id=%s",
                job_id,
                invoice_id,
            )
            self.repository.update_status(
                invoice_id=invoice_id,
                status=ProcessingState.FAILED,
                updated_at=datetime.now(timezone.utc).isoformat(),
            )
            self.repository.save_audit_event(
                AuditEvent(
                    invoice_id=invoice_id,
                    job_id=job_id,
                    event_type=AuditEventType.PROCESSING_FAILED,
                    details={"error_category": "MISSING_INVOICE_DATA"},
                )
            )
            return False

        # 6. Execute Agent & Decision Guard Pipeline
        try:
            decision, metadata = run_verification_workflow(
                invoice=resolved_invoice,
                history=history,
                policy_config=policy_config,
                settings=self.settings,
            )
        except Exception as exc:
            logger.exception(
                "Agent execution failed. job_id=%s, invoice_id=%s, error=%s",
                job_id,
                invoice_id,
                type(exc).__name__,
            )
            self.repository.update_status(
                invoice_id=invoice_id,
                status=ProcessingState.FAILED,
                updated_at=datetime.now(timezone.utc).isoformat(),
            )
            self.repository.save_audit_event(
                AuditEvent(
                    invoice_id=invoice_id,
                    job_id=job_id,
                    event_type=AuditEventType.PROCESSING_FAILED,
                    details={"error_category": "AGENT_EXECUTION_FAILURE", "exception": type(exc).__name__},
                )
            )
            return False

        # 7. Emit Tool Execution & Verification Audit Events
        for tool_name in metadata.tools_called:
            self.repository.save_audit_event(
                AuditEvent(
                    invoice_id=invoice_id,
                    job_id=job_id,
                    event_type=AuditEventType.TOOL_EXECUTED,
                    details={"tool": tool_name},
                )
            )

        self.repository.save_audit_event(
            AuditEvent(
                invoice_id=invoice_id,
                job_id=job_id,
                event_type=AuditEventType.VERIFICATION_COMPLETED,
                details={
                    "decision": decision.decision.value,
                    "confidence": decision.confidence,
                    "risk_level": decision.risk_level.value if decision.risk_level else None,
                    "risk_score": decision.risk_score,
                },
            )
        )

        if metadata.was_overridden:
            self.repository.save_audit_event(
                AuditEvent(
                    invoice_id=invoice_id,
                    job_id=job_id,
                    event_type=AuditEventType.DECISION_GUARDED,
                    details={"override_reason": metadata.override_reason},
                )
            )

        # 8. Determine Final Lifecycle State
        final_state = decision_to_state(decision.decision)

        # 9. Persist Final State to DynamoDB
        finish_now = datetime.now(timezone.utc).isoformat()
        final_record = InvoiceRecord(
            invoice_id=resolved_invoice.invoice_id,
            invoice_number=resolved_invoice.invoice_number,
            vendor_id=resolved_invoice.vendor_id,
            vendor_name=resolved_invoice.vendor_name,
            invoice_date=resolved_invoice.invoice_date.isoformat() if hasattr(resolved_invoice.invoice_date, "isoformat") else str(resolved_invoice.invoice_date),
            currency=resolved_invoice.currency,
            subtotal=resolved_invoice.subtotal,
            tax=resolved_invoice.tax,
            discount=resolved_invoice.discount,
            total=resolved_invoice.total,
            document_s3_key=job.s3_key,
            processing_status=final_state,
            decision=decision.decision,
            risk_level=decision.risk_level,
            risk_score=decision.risk_score,
            created_at=existing_record.created_at if existing_record else now_iso,
            updated_at=finish_now,
            agent_run_id=metadata.agent_run_id,
            verification_summary=decision.model_dump(),
            idempotency_key=job_id,
        )

        try:
            self.repository.save_record(final_record)
        except Exception as exc:
            logger.exception(
                "Persistence failed for completed invoice. job_id=%s, invoice_id=%s",
                job_id,
                invoice_id,
            )
            # CRITICAL: DO NOT ACK SQS MESSAGE IF PERSISTENCE FAILS
            return False

        self.repository.save_audit_event(
            AuditEvent(
                invoice_id=invoice_id,
                job_id=job_id,
                event_type=AuditEventType.PROCESSING_COMPLETED,
                details={"final_state": final_state.value, "decision": decision.decision.value},
            )
        )

        # 10. Acknowledge and delete message from queue ONLY after persistence succeeds
        if receipt_handle:
            try:
                self.job_queue.ack_job(receipt_handle)
            except Exception:
                logger.warning(
                    "Failed to delete SQS message after successful persistence. job_id=%s",
                    job_id,
                )

        logger.info(
            "Worker successfully processed invoice. job_id=%s, invoice_id=%s, state=%s, decision=%s",
            job_id,
            invoice_id,
            final_state.value,
            decision.decision.value,
        )
        return True
