"""Accounts Payable invoice ingestion, document attachment, status, audit, and review routes."""

import logging
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, File, Request, Response, UploadFile, status

from app.api.dependencies import (
    get_current_settings,
    get_document_store,
    get_invoice_repository,
    get_job_queue,
    require_api_key,
)
from app.api.errors import (
    ConflictError,
    InvalidInvoiceError,
    InvoiceNotFoundError,
    PayloadTooLargeError,
)
from app.api.schemas import (
    AuditEventResponse,
    DocumentUploadResponse,
    HumanReviewRequest,
    HumanReviewResponse,
    InvoiceCreateRequest,
    InvoiceCreateResponse,
    InvoiceStatusResponse,
    InvoiceListItemResponse,
    InvoiceListResponse,
)
from app.config import Settings
from app.models.audit import AuditEvent, AuditEventType
from app.models.decision import AgentDecision
from app.models.invoice import Invoice
from app.models.job import JobStatus, ProcessingJob
from app.models.persistence import InvoiceRecord
from app.services.interfaces import DocumentStore, InvoiceRepository, JobQueue
from app.services.s3 import sanitize_filename
from app.services.state import TERMINAL_STATES, ProcessingState

logger = logging.getLogger("ledgerguard.api.invoices")

router = APIRouter(prefix="/invoices", tags=["Invoices"])


@router.post(
    "",
    response_model=InvoiceCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest and queue invoice",
    description="Ingest structured invoice data and publish a background processing job to SQS.",
)
async def create_invoice(
    request: Request,
    response: Response,
    payload: InvoiceCreateRequest,
    settings: Annotated[Settings, Depends(get_current_settings)],
    repository: Annotated[InvoiceRepository, Depends(get_invoice_repository)],
    job_queue: Annotated[JobQueue, Depends(get_job_queue)],
    _api_key: Annotated[str | None, Depends(require_api_key)],
) -> InvoiceCreateResponse:
    req_id = getattr(request.state, "request_id", "unknown")
    logger.info(
        "Invoice ingestion requested. invoice_id=%s, vendor_id=%s, request_id=%s",
        payload.invoice_id,
        payload.vendor_id,
        req_id,
    )

    # 1. Check idempotency against repository
    existing = repository.get_record(payload.invoice_id)
    if existing is not None:
        if existing.processing_status in TERMINAL_STATES:
            logger.warning(
                "[IDEMPOTENCY] Rejected duplicate submission for terminal invoice %s (state=%s). request_id=%s",
                payload.invoice_id,
                existing.processing_status.value,
                req_id,
            )
            raise ConflictError(
                f"Invoice '{payload.invoice_id}' has already reached terminal state "
                f"'{existing.processing_status.value}' and cannot be re-ingested."
            )

        # If already QUEUED or PROCESSING, return existing job information safely
        logger.info(
            "[IDEMPOTENCY] Returning existing queued/processing state for invoice %s. request_id=%s",
            payload.invoice_id,
            req_id,
        )
        response.status_code = status.HTTP_200_OK
        return InvoiceCreateResponse(
            invoice_id=existing.invoice_id,
            job_id=existing.idempotency_key or f"job_{existing.invoice_id}",
            status=existing.processing_status.value,
            processing_status=existing.processing_status.value,
            created_at=existing.created_at,
        )

    # 2. Construct domain Invoice
    invoice = Invoice(
        invoice_id=payload.invoice_id,
        invoice_number=payload.invoice_number,
        vendor_id=payload.vendor_id,
        vendor_name=payload.vendor_name,
        customer_name=payload.customer_name,
        invoice_date=payload.invoice_date,
        currency=payload.currency,
        subtotal=payload.subtotal,
        tax=payload.tax,
        discount=payload.discount,
        total=payload.total,
        line_items=payload.line_items,
        metadata=payload.metadata,
    )

    # 3. Create processing job and persisted initial record
    job = ProcessingJob(
        invoice_id=invoice.invoice_id,
        s3_bucket=settings.LEDGERGUARD_S3_BUCKET,
    )

    record = InvoiceRecord.from_invoice(
        invoice=invoice,
        status=ProcessingState.QUEUED,
        idempotency_key=payload.idempotency_key or job.job_id,
    )

    # Persist record in DynamoDB
    repository.save_record(record)

    # Persist initial audit event
    repository.save_audit_event(
        AuditEvent(
            invoice_id=invoice.invoice_id,
            job_id=job.job_id,
            event_type=AuditEventType.JOB_QUEUED,
            source="ledgerguard_api",
            details={
                "request_id": req_id,
                "vendor_id": invoice.vendor_id,
                "currency": invoice.currency,
                "total": str(invoice.total) if invoice.total is not None else None,
            },
        )
    )

    # 4. Dispatch job to SQS queue
    job_queue.send_job(job)

    logger.info(
        "Invoice successfully queued for processing. invoice_id=%s, job_id=%s, request_id=%s",
        invoice.invoice_id,
        job.job_id,
        req_id,
    )

    return InvoiceCreateResponse(
        invoice_id=invoice.invoice_id,
        job_id=job.job_id,
        status=ProcessingState.QUEUED.value,
        processing_status=ProcessingState.QUEUED.value,
        created_at=record.created_at,
    )


@router.post(
    "/{invoice_id}/document",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_200_OK,
    summary="Attach invoice document",
    description="Upload source invoice document to S3 and associate with invoice record.",
)
async def upload_document(
    request: Request,
    invoice_id: str,
    settings: Annotated[Settings, Depends(get_current_settings)],
    document_store: Annotated[DocumentStore, Depends(get_document_store)],
    repository: Annotated[InvoiceRepository, Depends(get_invoice_repository)],
    _api_key: Annotated[str | None, Depends(require_api_key)],
    file: UploadFile = File(...),
) -> DocumentUploadResponse:
    req_id = getattr(request.state, "request_id", "unknown")
    logger.info("Document upload initiated. invoice_id=%s, request_id=%s", invoice_id, req_id)

    # 1. Validate invoice existence
    record = repository.get_record(invoice_id)
    if record is None:
        raise InvoiceNotFoundError(f"Invoice '{invoice_id}' not found.")

    # 2. Validate filename
    if not file.filename or not file.filename.strip():
        raise InvalidInvoiceError("Uploaded file must specify a valid filename.")

    # 3. Read and check file content length
    content = await file.read()
    if len(content) == 0:
        raise InvalidInvoiceError("Uploaded file content cannot be empty.")

    max_bytes = settings.MAX_DOCUMENT_SIZE_BYTES
    if len(content) > max_bytes:
        logger.warning(
            "Document upload exceeded size limit. size=%d, max=%d, invoice_id=%s, request_id=%s",
            len(content),
            max_bytes,
            invoice_id,
            req_id,
        )
        raise PayloadTooLargeError(
            f"Uploaded document size ({len(content)} bytes) exceeds configured maximum ({max_bytes} bytes)."
        )

    # 4. Sanitize filename to prevent directory traversal
    safe_name = sanitize_filename(file.filename)

    # 5. Upload to S3
    s3_key = document_store.upload_document(
        invoice_id=invoice_id,
        filename=safe_name,
        data=content,
        content_type=file.content_type or "application/pdf",
    )

    # 6. Update record with S3 key
    record.document_s3_key = s3_key
    record.updated_at = datetime.now(timezone.utc).isoformat()
    repository.save_record(record)

    # 7. Generate audit event
    repository.save_audit_event(
        AuditEvent(
            invoice_id=invoice_id,
            job_id=record.idempotency_key,
            event_type=AuditEventType.DOCUMENT_RECEIVED,
            source="ledgerguard_api",
            details={
                "s3_key": s3_key,
                "filename": safe_name,
                "file_size": len(content),
                "request_id": req_id,
            },
        )
    )

    logger.info(
        "Document uploaded and linked to invoice. invoice_id=%s, s3_key=%s, size=%d, request_id=%s",
        invoice_id,
        s3_key,
        len(content),
        req_id,
    )

    return DocumentUploadResponse(
        invoice_id=invoice_id,
        s3_key=s3_key,
        filename=safe_name,
        file_size=len(content),
        uploaded_at=record.updated_at,
    )


@router.get(
    "/{invoice_id}",
    response_model=InvoiceStatusResponse,
    summary="Get invoice status and verification verdict",
    description="Query DynamoDB for invoice processing lifecycle state and agent verification verdict.",
)
async def get_invoice_status(
    invoice_id: str,
    repository: Annotated[InvoiceRepository, Depends(get_invoice_repository)],
    _api_key: Annotated[str | None, Depends(require_api_key)],
) -> InvoiceStatusResponse:
    record = repository.get_record(invoice_id)
    if record is None:
        raise InvoiceNotFoundError(f"Invoice '{invoice_id}' not found.")

    return InvoiceStatusResponse(
        invoice_id=record.invoice_id,
        invoice_number=record.invoice_number,
        vendor_id=record.vendor_id,
        vendor_name=record.vendor_name,
        customer_name=record.customer_name,
        invoice_date=record.invoice_date,
        currency=record.currency,
        subtotal=record.subtotal,
        tax=record.tax,
        discount=record.discount,
        total=record.total,
        document_s3_key=record.document_s3_key,
        processing_status=record.processing_status.value,
        decision=record.decision.value if record.decision else None,
        risk_level=record.risk_level.value if record.risk_level else None,
        risk_score=record.risk_score,
        agent_run_id=record.agent_run_id,
        verification_summary=record.verification_summary,
        original_decision=record.original_decision.value if record.original_decision else None,
        review_decision=record.review_decision,
        reviewer=record.reviewer,
        review_timestamp=record.review_timestamp,
        review_comment=record.review_comment,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


@router.get(
    "/{invoice_id}/audit",
    response_model=list[AuditEventResponse],
    summary="Get invoice audit trail",
    description="Query chronological, immutable audit trail events for compliance inspection.",
)
async def get_invoice_audit_trail(
    invoice_id: str,
    repository: Annotated[InvoiceRepository, Depends(get_invoice_repository)],
    _api_key: Annotated[str | None, Depends(require_api_key)],
) -> list[AuditEventResponse]:
    record = repository.get_record(invoice_id)
    if record is None:
        raise InvoiceNotFoundError(f"Invoice '{invoice_id}' not found.")

    events = repository.get_audit_events(invoice_id)
    return [
        AuditEventResponse(
            event_id=ev.event_id,
            invoice_id=ev.invoice_id,
            job_id=ev.job_id,
            event_type=ev.event_type.value if hasattr(ev.event_type, "value") else str(ev.event_type),
            timestamp=ev.timestamp,
            source=ev.source,
            details=ev.details,
        )
        for ev in events
    ]


@router.post(
    "/{invoice_id}/review",
    response_model=HumanReviewResponse,
    summary="Record human review action",
    description="Apply a controlled manual review action to an invoice in MANUAL_REVIEW state.",
)
async def submit_human_review(
    request: Request,
    invoice_id: str,
    payload: HumanReviewRequest,
    repository: Annotated[InvoiceRepository, Depends(get_invoice_repository)],
    _api_key: Annotated[str | None, Depends(require_api_key)],
) -> HumanReviewResponse:
    req_id = getattr(request.state, "request_id", "unknown")
    logger.info(
        "Human review submitted. invoice_id=%s, reviewer=%s, action=%s, request_id=%s",
        invoice_id,
        payload.reviewer,
        payload.action,
        req_id,
    )

    record = repository.get_record(invoice_id)
    if record is None:
        raise InvoiceNotFoundError(f"Invoice '{invoice_id}' not found.")

    # Validate against current lifecycle state
    if record.processing_status in (ProcessingState.RECEIVED, ProcessingState.QUEUED, ProcessingState.PROCESSING):
        raise ConflictError(
            f"Invoice '{invoice_id}' is currently '{record.processing_status.value}'. "
            f"Review is only permitted after automated processing finishes."
        )

    if record.processing_status == ProcessingState.AUTO_APPROVED:
        raise ConflictError(
            f"Invoice '{invoice_id}' is already AUTO_APPROVED and does not require human review."
        )

    if record.processing_status == ProcessingState.BLOCKED:
        raise ConflictError(
            f"Invoice '{invoice_id}' is BLOCKED by safety guard and cannot be overridden by review."
        )

    if record.processing_status == ProcessingState.FAILED:
        raise ConflictError(
            f"Invoice '{invoice_id}' is in FAILED state. It must be reprocessed before review."
        )

    # Preserve original automated decision
    orig_decision = record.original_decision or record.decision or AgentDecision.MANUAL_REVIEW
    now_iso = datetime.now(timezone.utc).isoformat()

    record.original_decision = orig_decision
    record.review_decision = payload.action
    record.reviewer = payload.reviewer
    record.review_timestamp = now_iso
    record.review_comment = payload.comment
    record.updated_at = now_iso

    # Persist updated record
    repository.save_record(record)

    # Emit append-only audit event
    repository.save_audit_event(
        AuditEvent(
            invoice_id=invoice_id,
            job_id=record.idempotency_key,
            event_type=AuditEventType.HUMAN_REVIEW_RECORDED,
            source="ledgerguard_api",
            details={
                "reviewer": payload.reviewer,
                "action": payload.action,
                "comment": payload.comment,
                "original_decision": orig_decision.value if hasattr(orig_decision, "value") else str(orig_decision),
                "request_id": req_id,
            },
        )
    )

    logger.info(
        "Human review recorded successfully. invoice_id=%s, reviewer=%s, action=%s, request_id=%s",
        invoice_id,
        payload.reviewer,
        payload.action,
        req_id,
    )

    return HumanReviewResponse(
        invoice_id=invoice_id,
        original_decision=orig_decision.value if hasattr(orig_decision, "value") else str(orig_decision),
        review_decision=payload.action,
        reviewer=payload.reviewer,
        review_timestamp=now_iso,
        review_comment=payload.comment,
        status=record.processing_status.value,
    )

@router.get(
    "",
    response_model=InvoiceListResponse,
    summary="List invoices",
    description="Query persisted invoice records with search, status filtering, and pagination.",
)
async def list_invoices(
    request: Request,
    repository: Annotated[InvoiceRepository, Depends(get_invoice_repository)],
    _api_key: Annotated[str | None, Depends(require_api_key)],
    limit: int = 50,
    offset: int = 0,
    status: ProcessingState | None = None,
    vendor_id: str | None = None,
    search: str | None = None,
) -> InvoiceListResponse:
    req_id = getattr(request.state, "request_id", "unknown")
    clamped_limit = max(1, min(limit, 100))
    clamped_offset = max(0, offset)
    logger.info(
        "Listing invoices. limit=%d, offset=%d, status=%s, vendor_id=%s, search=%s, request_id=%s",
        clamped_limit,
        clamped_offset,
        status.value if status else None,
        vendor_id,
        search,
        req_id,
    )

    records = repository.list_records(
        limit=clamped_limit,
        offset=clamped_offset,
        status=status,
        vendor_id=vendor_id,
        search=search,
    )
    total_count = repository.count_records(
        status=status,
        vendor_id=vendor_id,
        search=search,
    )

    items = [
        InvoiceListItemResponse(
            invoice_id=r.invoice_id,
            invoice_number=r.invoice_number,
            vendor_id=r.vendor_id,
            vendor_name=r.vendor_name,
            invoice_date=r.invoice_date,
            currency=r.currency,
            total=r.total,
            processing_status=r.processing_status.value,
            decision=r.decision.value if r.decision else None,
            risk_level=r.risk_level.value if r.risk_level else None,
            risk_score=r.risk_score,
            created_at=r.created_at,
            updated_at=r.updated_at,
            document_s3_key=r.document_s3_key,
            original_decision=r.original_decision.value if r.original_decision else None,
            review_decision=r.review_decision,
        )
        for r in records
    ]

    return InvoiceListResponse(
        items=items,
        total=total_count,
        limit=clamped_limit,
        offset=clamped_offset,
    )
