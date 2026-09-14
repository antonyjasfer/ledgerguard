"""Background worker processor executing the LedgerGuard invoice verification pipeline.

Coordinates SQS job polling, S3 document presence verification, autonomous PDF
extraction (Phase 8), deterministic tool orchestration, Decision Guard enforcement,
and durable DynamoDB state updates.

Strictly enforces transactional ordering:
State & Decision Persisted -> SQS Message Acknowledged.
Logs ONLY safe operational metadata, never credentials, raw PDFs, or payloads.
"""

import logging
import random
import threading
import time
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Sequence

from app.agent.orchestrator import run_verification_workflow
from app.config import Settings, get_settings
from app.models.audit import AuditEvent, AuditEventType
from app.models.batch import DocumentStatus
from app.models.decision import AgentDecision, VerificationDecision
from app.models.extraction import ExtractionField, ExtractionResult, ExtractionStatus
from app.models.invoice import Invoice
from app.models.job import JobStatus, ProcessingJob
from app.models.persistence import InvoiceRecord
from app.models.policy import PolicyConfig
from app.services.document_extraction import CompositeDocumentExtractor, DocumentExtractor
from app.services.interfaces import DocumentStore, InvoiceRepository, JobQueue, SecretProvider
from app.services.state import TERMINAL_STATES, ProcessingState
from app.services.vendor_context import VendorContextService

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
        extractor: DocumentExtractor | None = None,
        auto_extract: bool = False,
    ):
        self.document_store = document_store
        self.repository = repository
        self.job_queue = job_queue
        self.secret_provider = secret_provider
        self.settings = settings or get_settings()
        self.extractor = extractor or CompositeDocumentExtractor()
        self.vendor_service = VendorContextService()
        self.auto_extract = auto_extract
        self._extraction_semaphore = threading.Semaphore(self.settings.MAX_EXTRACTION_CONCURRENCY)
        self._gemma_semaphore = threading.Semaphore(self.settings.MAX_GEMMA_CONCURRENCY)

    def _run_workflow_with_bounded_retry(
        self,
        invoice: Invoice,
        history: Sequence[Invoice],
        policy_config: PolicyConfig | None,
        job: ProcessingJob,
    ) -> tuple[VerificationDecision, Any]:
        """Execute verification workflow within Gemma semaphore with exponential backoff on throttling.

        If retries are exhausted, falls back to deterministic AgentDecision.MANUAL_REVIEW.
        NEVER auto-approves on model failure!
        """
        max_retries = 3
        backoff_base = 0.5
        last_exception = None

        with self._gemma_semaphore:
            for attempt in range(1, max_retries + 1):
                try:
                    return run_verification_workflow(
                        invoice=invoice,
                        history=history,
                        policy_config=policy_config,
                        settings=self.settings,
                    )
                except Exception as exc:
                    last_exception = exc
                    exc_name = type(exc).__name__
                    is_throttled = "throttle" in str(exc).lower() or "429" in str(exc).lower() or "rate" in str(exc).lower() or "throttling" in exc_name.lower()
                    if is_throttled and attempt < max_retries:
                        sleep_time = (backoff_base * (2 ** (attempt - 1))) + random.uniform(0.1, 0.4)
                        logger.warning(
                            "Bedrock/Gemma throttled (attempt %d/%d). Backing off for %.2fs. Error: %s",
                            attempt, max_retries, sleep_time, exc
                        )
                        self._update_batch_counters(job.batch_id, retry=True)
                        time.sleep(sleep_time)
                    elif not is_throttled:
                        # Non-throttling exceptions should be raised to trigger standard failure handling
                        raise exc

            # If exhausted retries on throttling, use deterministic MANUAL_REVIEW fallback
            logger.error(
                "Model reasoning failed/exhausted retries (error=%s). Safely routing to MANUAL_REVIEW. Never auto-approving on failure.",
                last_exception,
            )
            from app.models.decision import EvidenceItem
            fallback_decision = VerificationDecision(
                decision=AgentDecision.MANUAL_REVIEW,
                confidence="INSUFFICIENT_EVIDENCE",
                summary=f"Model reasoning throttled/failed ({type(last_exception).__name__}). Safely routed to manual review.",
                evidence=[
                    EvidenceItem(source="THROTTLING_GUARD", finding="AUTOMATED_REASONING_THROTTLED", details={"error": str(last_exception)[:150]}),
                    EvidenceItem(source="DECISION_GUARD", finding="DETERMINISTIC_FALLBACK_TO_MANUAL_REVIEW", details={"action": "routed_to_review"}),
                ],
                risk_level=None,
                risk_score=50,
                tools_called=["deterministic_fallback"],
                requires_human=True,
                human_review_reason=f"MODEL_THROTTLED_FALLBACK_TO_REVIEW: {str(last_exception)[:150]}",
            )
            from app.agent.orchestrator import ExecutionMetadata
            fallback_metadata = ExecutionMetadata(
                provider=self.settings.LEDGERGUARD_MODEL_PROVIDER,
                model="fallback-throttled",
                tools_called=["deterministic_fallback"],
                decision=AgentDecision.MANUAL_REVIEW,
                was_overridden=True,
                override_reason="MODEL_THROTTLED_FALLBACK_TO_REVIEW",
            )
            return fallback_decision, fallback_metadata

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

        # Phase 7 & 8: Raw Document Job Handling
        if job.document_id:
            return self._process_raw_document_job(
                job=job,
                receipt_handle=receipt_handle,
                history=history,
                policy_config=policy_config,
            )

        # Standard Single-Invoice Pipeline (Phases 1-6)
        return self._process_structured_invoice_job(
            job=job,
            receipt_handle=receipt_handle,
            invoice_data=invoice_data,
            history=history,
            policy_config=policy_config,
        )

    def _process_raw_document_job(
        self,
        job: ProcessingJob,
        receipt_handle: str | None,
        history: Sequence[Invoice],
        policy_config: PolicyConfig | None,
    ) -> bool:
        """Handle Phase 7 ingestion and Phase 8 extraction."""
        job_id = job.job_id
        invoice_id = job.invoice_id
        batch_id = job.batch_id
        doc_id = job.document_id

        logger.info(
            "Worker handling raw document job. job_id=%s, batch_id=%s, document_id=%s",
            job_id,
            batch_id,
            doc_id,
        )

        # 1. S3 Presence Verification
        if not job.s3_key or not self.document_store.document_exists(job.s3_key):
            logger.error(
                "Missing S3 document artifact. job_id=%s, document_id=%s, key=%s",
                job_id,
                doc_id,
                job.s3_key,
            )
            if hasattr(self.repository, "get_document_record") and batch_id:
                doc_rec = self.repository.get_document_record(batch_id, doc_id)
                if doc_rec:
                    doc_rec.status = DocumentStatus.FAILED
                    doc_rec.error_code = "MISSING_S3_DOCUMENT"
                    doc_rec.error_message = f"Document key '{job.s3_key}' not found in S3"
                    self.repository.save_document_record(doc_rec)
            return False

        # Phase 7 Ingestion flow check:
        # If extraction is not explicitly requested via action='extract' and auto_extract is False,
        # complete Phase 7 ingestion behavior (set AWAITING_EXTRACTION and emit DOCUMENT_INGESTED).
        should_extract = self.auto_extract or getattr(job, "action", "") == "extract" or (job.metadata and job.metadata.get("action") == "extract")

        if not should_extract:
            self.repository.save_audit_event(
                AuditEvent(
                    invoice_id=invoice_id,
                    job_id=job_id,
                    event_type=AuditEventType.DOCUMENT_INGESTED,
                    details={
                        "batch_id": batch_id,
                        "document_id": doc_id,
                        "s3_key": job.s3_key,
                        "status": ProcessingState.AWAITING_EXTRACTION.value,
                    },
                )
            )

            try:
                existing_rec = self.repository.get_record(invoice_id)
                if existing_rec:
                    self.repository.update_status(
                        invoice_id=invoice_id,
                        status=ProcessingState.AWAITING_EXTRACTION,
                        updated_at=datetime.now(timezone.utc).isoformat(),
                    )
            except Exception:
                pass

            if receipt_handle:
                try:
                    self.job_queue.ack_job(receipt_handle)
                except Exception:
                    logger.warning("Failed to delete SQS message for doc %s", doc_id)

            logger.info("Raw document %s verified; state remains %s.", doc_id, ProcessingState.AWAITING_EXTRACTION.value)
            return True

        # Phase 8: Autonomous Extraction Execution
        self.repository.save_audit_event(
            AuditEvent(
                invoice_id=invoice_id,
                job_id=job_id,
                event_type=AuditEventType.DOCUMENT_INGESTED,
                details={
                    "batch_id": batch_id,
                    "document_id": doc_id,
                    "s3_key": job.s3_key,
                    "status": ProcessingState.EXTRACTING.value,
                },
            )
        )

        doc_rec = None
        if hasattr(self.repository, "get_document_record") and batch_id:
            doc_rec = self.repository.get_document_record(batch_id, doc_id)
            if doc_rec:
                doc_rec.status = DocumentStatus.EXTRACTING
                doc_rec.updated_at = datetime.now(timezone.utc).isoformat()
                self.repository.save_document_record(doc_rec)

        try:
            pdf_bytes = self.document_store.download_document(job.s3_key)
        except Exception as exc:
            logger.exception("Failed to download document from S3. key=%s, error=%s", job.s3_key, exc)
            if doc_rec:
                doc_rec.status = DocumentStatus.FAILED
                doc_rec.error_code = "S3_DOWNLOAD_ERROR"
                doc_rec.error_message = f"Failed to download document: {type(exc).__name__}"
                self.repository.save_document_record(doc_rec)
            return False

        self.repository.save_audit_event(
            AuditEvent(
                invoice_id=invoice_id,
                job_id=job_id,
                event_type=AuditEventType.EXTRACTION_STARTED,
                details={"extractor": getattr(self.extractor, "provider_name", "CompositeDocumentExtractor")},
            )
        )

        try:
            extraction_result: ExtractionResult = self.extractor.extract(
                pdf_bytes, metadata={"document_id": doc_id, "batch_id": batch_id}
            )
        except Exception as exc:
            logger.exception("Document extraction crashed for doc %s: %s", doc_id, exc)
            if doc_rec:
                doc_rec.status = DocumentStatus.EXTRACTION_FAILED
                doc_rec.error_code = "EXTRACTION_EXCEPTION"
                doc_rec.error_message = str(exc)[:200]
                self.repository.save_document_record(doc_rec)
            self.repository.save_audit_event(
                AuditEvent(
                    invoice_id=invoice_id,
                    job_id=job_id,
                    event_type=AuditEventType.EXTRACTION_FAILED,
                    details={"error": type(exc).__name__, "message": str(exc)[:200]},
                )
            )
            if receipt_handle:
                self.job_queue.ack_job(receipt_handle)
            return True

        # Persist Extraction Result
        if hasattr(self.repository, "save_extraction_result") and batch_id:
            try:
                self.repository.save_extraction_result(batch_id, doc_id, extraction_result)
            except Exception as exc:
                logger.warning("Could not persist full extraction result: %s", exc)

        # Record GEMMA_EXTRACTION_COMPLETED if extracted by Gemma
        if getattr(extraction_result, "extractor_provider", "") == "GemmaInvoiceExtractor":
            self.repository.save_audit_event(
                AuditEvent(
                    invoice_id=invoice_id,
                    job_id=job_id,
                    event_type=AuditEventType.GEMMA_EXTRACTION_COMPLETED,
                    details={
                        "extractor": extraction_result.extractor_provider,
                        "overall_confidence": extraction_result.overall_confidence,
                        "field_count": len(extraction_result.invoice_fields),
                        "line_items_count": len(extraction_result.line_items),
                    },
                )
            )

        # Check for failure
        if extraction_result.status == ExtractionStatus.FAILED:
            if doc_rec:
                doc_rec.status = DocumentStatus.EXTRACTION_FAILED
                doc_rec.extraction_status = extraction_result.status.value
                doc_rec.overall_confidence = extraction_result.overall_confidence
                doc_rec.extractor_provider = extraction_result.extractor_provider
                doc_rec.extractor_version = extraction_result.extractor_version
                doc_rec.error_code = "EXTRACTION_FAILED"
                doc_rec.error_message = "; ".join(extraction_result.errors) if extraction_result.errors else "Failed to extract text"
                self.repository.save_document_record(doc_rec)

            self.repository.save_audit_event(
                AuditEvent(
                    invoice_id=invoice_id,
                    job_id=job_id,
                    event_type=AuditEventType.EXTRACTION_FAILED,
                    details={"errors": extraction_result.errors},
                )
            )
            if receipt_handle:
                self.job_queue.ack_job(receipt_handle)
            return True

        # Low Confidence / Insufficient Data Handling -> Routes to MANUAL_REVIEW
        is_low_confidence = (
            extraction_result.status in (ExtractionStatus.INSUFFICIENT_CONFIDENCE, ExtractionStatus.INSUFFICIENT_DATA)
            or extraction_result.overall_confidence < 0.85
            or extraction_result.reconstructed_invoice is None
        )

        if is_low_confidence:
            logger.info(
                "Extraction requires human review. doc_id=%s, confidence=%.4f, status=%s",
                doc_id,
                extraction_result.overall_confidence,
                extraction_result.status.value,
            )
            if doc_rec:
                if extraction_result.status == ExtractionStatus.INSUFFICIENT_DATA:
                    doc_rec.status = DocumentStatus.INSUFFICIENT_DATA
                else:
                    doc_rec.status = DocumentStatus.INSUFFICIENT_CONFIDENCE
                doc_rec.extraction_status = extraction_result.status.value
                doc_rec.overall_confidence = extraction_result.overall_confidence
                doc_rec.extractor_provider = extraction_result.extractor_provider
                doc_rec.extractor_version = extraction_result.extractor_version
                doc_rec.extraction_summary = extraction_result.to_dynamodb_summary()
                self.repository.save_document_record(doc_rec)

            now_iso = datetime.now(timezone.utc).isoformat()
            review_record = InvoiceRecord(
                invoice_id=invoice_id,
                invoice_number=extraction_result.invoice_fields.get("invoice_number", ExtractionField(field_name="invoice_number")).value or "UNKNOWN",
                vendor_id="PENDING_REVIEW",
                vendor_name=extraction_result.invoice_fields.get("vendor_name", ExtractionField(field_name="vendor_name")).value or "UNKNOWN",
                invoice_date=str(extraction_result.invoice_fields.get("invoice_date", ExtractionField(field_name="invoice_date")).value or now_iso[:10]),
                currency=str(extraction_result.invoice_fields.get("currency", ExtractionField(field_name="currency")).value or "USD"),
                subtotal=extraction_result.computed_subtotal,
                tax=extraction_result.financials.get("tax", ExtractionField(field_name="tax")).value if isinstance(extraction_result.financials.get("tax"), ExtractionField) else None,
                discount=extraction_result.financials.get("discount", ExtractionField(field_name="discount")).value if isinstance(extraction_result.financials.get("discount"), ExtractionField) else None,
                shipping=extraction_result.financials.get("shipping", ExtractionField(field_name="shipping")).value if isinstance(extraction_result.financials.get("shipping"), ExtractionField) else None,
                total=extraction_result.declared_total,
                document_s3_key=job.s3_key,
                processing_status=ProcessingState.MANUAL_REVIEW,
                decision=AgentDecision.MANUAL_REVIEW,
                created_at=now_iso,
                updated_at=now_iso,
                verification_summary={
                    "reason": "Extraction flagged for manual review due to low confidence or missing required fields",
                    "extraction_status": extraction_result.status.value,
                    "confidence": extraction_result.overall_confidence,
                    "warnings": extraction_result.warnings,
                },
            )
            try:
                self.repository.save_record(review_record)
            except Exception as exc:
                logger.warning("Could not persist review InvoiceRecord: %s", exc)

            self.repository.save_audit_event(
                AuditEvent(
                    invoice_id=invoice_id,
                    job_id=job_id,
                    event_type=AuditEventType.INSUFFICIENT_CONFIDENCE,
                    details={
                        "status": extraction_result.status.value,
                        "overall_confidence": extraction_result.overall_confidence,
                        "warnings": extraction_result.warnings,
                    },
                )
            )
            self.repository.save_audit_event(
                AuditEvent(
                    invoice_id=invoice_id,
                    job_id=job_id,
                    event_type=AuditEventType.EXTRACTION_COMPLETED,
                    details={
                        "status": ProcessingState.MANUAL_REVIEW.value,
                        "overall_confidence": extraction_result.overall_confidence,
                        "warnings": extraction_result.warnings,
                    },
                )
            )

            self._update_batch_counters(batch_id, low_confidence=True, manual_review=True)
            if receipt_handle:
                self.job_queue.ack_job(receipt_handle)
            return True

        # Successful Extraction & Reconstructed Invoice
        reconstructed_invoice = extraction_result.reconstructed_invoice
        matched_vendor = self.vendor_service.get_vendor(reconstructed_invoice.vendor_name)
        if matched_vendor:
            reconstructed_invoice.vendor_id = matched_vendor.vendor_id
            reconstructed_invoice.vendor_name = matched_vendor.legal_name
        else:
            reconstructed_invoice.vendor_id = "UNKNOWN_VENDOR"

        if doc_rec:
            doc_rec.status = DocumentStatus.EXTRACTION_VALIDATED
            doc_rec.extraction_status = extraction_result.status.value
            doc_rec.overall_confidence = extraction_result.overall_confidence
            doc_rec.extractor_provider = extraction_result.extractor_provider
            doc_rec.extractor_version = extraction_result.extractor_version
            doc_rec.extracted_invoice_id = reconstructed_invoice.invoice_id
            doc_rec.extraction_summary = extraction_result.to_dynamodb_summary()
            self.repository.save_document_record(doc_rec)

        self.repository.save_audit_event(
            AuditEvent(
                invoice_id=invoice_id,
                job_id=job_id,
                event_type=AuditEventType.EXTRACTION_VALIDATED,
                details={
                    "extracted_invoice_id": reconstructed_invoice.invoice_id,
                    "vendor_id": reconstructed_invoice.vendor_id,
                    "total": str(reconstructed_invoice.total),
                    "confidence": extraction_result.overall_confidence,
                },
            )
        )

        # Feed Reconstructed Invoice Directly into Existing Verification Pipeline
        if doc_rec:
            doc_rec.status = DocumentStatus.PROCESSING
            self.repository.save_document_record(doc_rec)

        success = self._process_structured_invoice_job(
            job=job,
            receipt_handle=receipt_handle,
            invoice_data=reconstructed_invoice,
            history=history,
            policy_config=policy_config,
        )

        if success and doc_rec:
            final_inv = self.repository.get_record(reconstructed_invoice.invoice_id)
            if final_inv:
                try:
                    doc_rec.status = DocumentStatus(final_inv.processing_status.value)
                    self.repository.save_document_record(doc_rec)
                except Exception:
                    pass
                auto_approved = final_inv.processing_status == ProcessingState.AUTO_APPROVED
                manual_rev = final_inv.processing_status == ProcessingState.MANUAL_REVIEW
                blocked = final_inv.processing_status == ProcessingState.BLOCKED
                self._update_batch_counters(
                    batch_id,
                    extracted=True,
                    auto_approved=auto_approved,
                    manual_review=manual_rev,
                    blocked=blocked,
                )

        return success

    def _process_structured_invoice_job(
        self,
        job: ProcessingJob,
        receipt_handle: str | None,
        invoice_data: Invoice | None,
        history: Sequence[Invoice],
        policy_config: PolicyConfig | None,
    ) -> bool:
        """Standard verification workflow for structured invoices (Phases 1-6)."""
        job_id = job.job_id
        invoice_id = job.invoice_id

        # 1. Idempotency Check
        if self.repository.is_already_processed(invoice_id):
            logger.info(
                "[IDEMPOTENCY] Invoice '%s' has already reached terminal state. Skipping duplicate execution for job '%s'.",
                invoice_id,
                job_id,
            )
            self.repository.save_audit_event(
                AuditEvent(
                    invoice_id=invoice_id,
                    job_id=job_id,
                    event_type=AuditEventType.PROCESSING_COMPLETED,
                    details={"status": "already_processed", "job_id": job_id},
                )
            )
            if receipt_handle:
                self.job_queue.ack_job(receipt_handle)
            return True

        # 2. Transition to PROCESSING state
        now_iso = datetime.now(timezone.utc).isoformat()
        self.repository.save_audit_event(
            AuditEvent(
                invoice_id=invoice_id,
                job_id=job_id,
                event_type=AuditEventType.PROCESSING_STARTED,
                details={"attempt": job.attempt, "s3_key": job.s3_key},
            )
        )

        existing_record = self.repository.get_record(invoice_id)
        if existing_record is not None:
            try:
                self.repository.update_status(
                    invoice_id=invoice_id,
                    status=ProcessingState.PROCESSING,
                    updated_at=now_iso,
                )
            except Exception as exc:
                logger.exception("Failed to update status in repository: %s", exc)
                return False

        # 3. Source document presence check (if S3 key provided)
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
                return False

            self.repository.save_audit_event(
                AuditEvent(
                    invoice_id=invoice_id,
                    job_id=job_id,
                    event_type=AuditEventType.DOCUMENT_RECEIVED,
                    details={"s3_bucket": job.s3_bucket, "s3_key": job.s3_key},
                )
            )

        # 4. Resolve Invoice Data
        resolved_invoice = invoice_data
        if resolved_invoice is None and existing_record is not None:
            try:
                resolved_invoice = existing_record.to_invoice()
            except Exception as exc:
                logger.warning("Could not reconstruct Invoice from existing record %s: %s", invoice_id, exc)

        if resolved_invoice is None:
            logger.error("No invoice data available for processing. job_id=%s, invoice_id=%s", job_id, invoice_id)
            self.repository.update_status(
                invoice_id=invoice_id,
                status=ProcessingState.FAILED,
                updated_at=now_iso,
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

        # 5. Execute Agent & Decision Guard Pipeline
        try:
            decision, metadata = self._run_workflow_with_bounded_retry(
                invoice=resolved_invoice,
                history=history,
                policy_config=policy_config,
                job=job,
            )
        except Exception as exc:
            logger.exception("Agent execution failed. job_id=%s, invoice_id=%s: %s", job_id, invoice_id, exc)
            self.repository.update_status(
                invoice_id=invoice_id,
                status=ProcessingState.FAILED,
                updated_at=now_iso,
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

        # 6. Emit Tool Execution & Verification Audit Events
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

        # 7. Determine Final Lifecycle State
        final_state = decision_to_state(decision.decision)

        # 8. Persist Final State to DynamoDB
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
            shipping=resolved_invoice.shipping,
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
            logger.exception("Persistence failed for completed invoice. job_id=%s, invoice_id=%s: %s", job_id, invoice_id, exc)
            return False

        self.repository.save_audit_event(
            AuditEvent(
                invoice_id=invoice_id,
                job_id=job_id,
                event_type=AuditEventType.PROCESSING_COMPLETED,
                details={"final_state": final_state.value, "decision": decision.decision.value},
            )
        )

        # 9. Acknowledge SQS message
        if receipt_handle:
            try:
                self.job_queue.ack_job(receipt_handle)
            except Exception:
                logger.warning("Failed to delete SQS message after successful persistence. job_id=%s", job_id)

        logger.info(
            "Worker successfully processed invoice. job_id=%s, invoice_id=%s, state=%s, decision=%s",
            job_id,
            invoice_id,
            final_state.value,
            decision.decision.value,
        )
        return True

    def _update_batch_counters(
        self,
        batch_id: str | None,
        extracted: bool = False,
        low_confidence: bool = False,
        auto_approved: bool = False,
        manual_review: bool = False,
        blocked: bool = False,
        failed: bool = False,
        retry: bool = False,
    ) -> None:
        """Increment batch counters safely and update progress timestamps."""
        if not batch_id or not hasattr(self.repository, "get_batch") or not hasattr(self.repository, "save_batch"):
            return
        try:
            batch = self.repository.get_batch(batch_id)
            if not batch:
                return
            now_iso = datetime.now(timezone.utc).isoformat()
            if not batch.started_at:
                batch.started_at = now_iso
            batch.last_progress_at = now_iso

            if retry:
                batch.retry_count += 1
                self.repository.save_batch(batch)
                return

            if extracted:
                batch.extracted_count += 1
            if low_confidence:
                batch.low_confidence_count += 1
            if auto_approved:
                batch.auto_approved_count += 1
            if manual_review:
                batch.manual_review_count += 1
            if blocked:
                batch.blocked_count += 1
            if failed:
                batch.failed_count += 1
                batch.processing_failed += 1

            batch.completed_count += 1
            if batch.completed_count + batch.duplicate_count + batch.rejected_count >= batch.document_count:
                batch.completed_at = now_iso
            batch.finalize_status()
            self.repository.save_batch(batch)
        except Exception as exc:
            logger.warning("Could not update batch counters for %s: %s", batch_id, exc)
