"""FastAPI router for bulk invoice ingestion and batch lifecycle management in LedgerGuard.

Supports multi-document ingestion, file validation, SHA-256 deduplication,
S3 storage, DynamoDB persistence, SQS job dispatch, autonomous extraction,
and human field correction review.
"""

from datetime import datetime, timezone
from decimal import Decimal
import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status

from app.api.dependencies import (
    get_batch_repository,
    get_document_store,
    get_invoice_repository,
    get_job_queue,
    require_api_key,
)
from app.api.schemas import (
    BatchCreateRequest,
    BatchDocumentsResponse,
    BatchListResponse,
    BatchProgressResponse,
    BatchResponse,
    BatchResumeResponse,
    DocumentCorrectionRequest,
    DocumentIngestionResponse,
    ExtractionResponse,
)
from app.models.audit import AuditEvent, AuditEventType
from app.models.batch import BatchRecord, BatchStatus, DocumentIngestionRecord, DocumentStatus
from app.models.decision import AgentDecision
from app.models.extraction import ExtractionField, ExtractionResult, ExtractionStatus
from app.models.job import ProcessingJob
from app.models.persistence import InvoiceRecord
from app.services.batch_validator import (
    compute_sha256,
    generate_batch_key,
    sanitize_document_filename,
    validate_batch_files,
    validate_single_file,
)
from app.services.document_extraction import CompositeDocumentExtractor
from app.services.interfaces import BatchRepository, DocumentStore, InvoiceRepository, JobQueue
from app.services.state import ProcessingState
from app.services.vendor_context import VendorContextService

logger = logging.getLogger("ledgerguard.api.batches")

router = APIRouter(prefix="/batches", tags=["Batch Ingestion"])


def _doc_to_response(doc: DocumentIngestionRecord) -> DocumentIngestionResponse:
    """Convert domain DocumentIngestionRecord to DocumentIngestionResponse schema."""
    return DocumentIngestionResponse(
        document_id=doc.document_id,
        batch_id=doc.batch_id,
        original_filename=doc.original_filename,
        safe_filename=doc.safe_filename,
        content_type=doc.content_type,
        file_size=doc.file_size,
        document_hash=doc.document_hash,
        s3_key=doc.s3_key,
        status=doc.status.value,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
        error_code=doc.error_code,
        error_message=doc.error_message,
        matched_document_id=doc.matched_document_id,
        matched_batch_id=doc.matched_batch_id,
        duplicate_reason=doc.duplicate_reason,
        idempotency_key=doc.idempotency_key,
        extraction_status=doc.extraction_status,
        overall_confidence=doc.overall_confidence,
        extractor_provider=doc.extractor_provider,
        extractor_version=doc.extractor_version,
        extracted_invoice_id=doc.extracted_invoice_id,
        extraction_summary=doc.extraction_summary,
    )


def _batch_to_response(batch: BatchRecord, docs: list[DocumentIngestionRecord] | None = None) -> BatchResponse:
    """Convert domain BatchRecord to BatchResponse schema."""
    doc_responses = [_doc_to_response(d) for d in docs] if docs else []
    return BatchResponse(
        batch_id=batch.batch_id,
        status=batch.status.value,
        source=batch.source,
        created_at=batch.created_at,
        updated_at=batch.updated_at,
        document_count=batch.document_count,
        received_count=batch.received_count,
        accepted_count=batch.accepted_count,
        rejected_count=batch.rejected_count,
        duplicate_count=batch.duplicate_count,
        failed_count=batch.failed_count,
        extracted_count=batch.extracted_count,
        low_confidence_count=batch.low_confidence_count,
        extraction_failed_count=batch.extraction_failed_count,
        queued_count=batch.queued_count,
        processing_count=batch.processing_count,
        completed_count=batch.completed_count,
        auto_approved_count=batch.auto_approved_count,
        manual_review_count=batch.manual_review_count,
        blocked_count=batch.blocked_count,
        error_count=batch.error_count,
        documents=doc_responses,
    )


@router.post(
    "",
    response_model=BatchResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new invoice ingestion batch",
)
def create_batch(
    request: BatchCreateRequest,
    batch_repo: Annotated[BatchRepository, Depends(get_batch_repository)],
    _auth: Annotated[str | None, Depends(require_api_key)] = None,
) -> BatchResponse:
    """Initialize an authoritative batch metadata record for bulk ingestion."""
    batch = BatchRecord(
        source=request.source,
        document_count=request.document_count,
        status=BatchStatus.RECEIVED,
    )
    batch_repo.save_batch(batch)
    logger.info("Created batch record %s (source=%s).", batch.batch_id, batch.source)
    return _batch_to_response(batch)


async def _process_batch_upload(
    files: list[UploadFile],
    batch_id: str | None,
    source: str,
    batch_repo: BatchRepository,
    doc_store: DocumentStore,
    job_queue: JobQueue,
) -> BatchResponse:
    """Core upload and ingestion processing shared by /upload and /{batch_id}/upload."""
    if batch_id:
        batch = batch_repo.get_batch(batch_id)
        if not batch:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Batch '{batch_id}' not found.",
            )
    else:
        batch = BatchRecord(source=source, status=BatchStatus.RECEIVED)
        batch_repo.save_batch(batch)

    batch.document_count += len(files)
    batch.received_count += len(files)
    batch.status = BatchStatus.UPLOADING

    processed_docs: list[DocumentIngestionRecord] = []

    for upload_file in files:
        raw_name = upload_file.filename or "unknown.pdf"
        safe_fn = sanitize_document_filename(raw_name)

        try:
            data = await upload_file.read()
        except Exception as exc:
            logger.warning("Could not read uploaded file %s: %s", raw_name, exc)
            data = b""

        doc_hash = compute_sha256(data) if data else "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

        doc_rec = DocumentIngestionRecord(
            batch_id=batch.batch_id,
            original_filename=raw_name,
            safe_filename=safe_fn,
            content_type=upload_file.content_type or "application/pdf",
            file_size=len(data),
            document_hash=doc_hash,
            status=DocumentStatus.VALIDATING,
        )

        is_valid, err_code, err_msg = validate_single_file(filename=raw_name, file_size=len(data), content_type=upload_file.content_type)
        if not is_valid:
            doc_rec.status = DocumentStatus.REJECTED
            doc_rec.error_code = err_code
            doc_rec.error_message = err_msg
            batch.rejected_count += 1
            batch.error_count += 1
            batch_repo.save_document_record(doc_rec)
            processed_docs.append(doc_rec)
            logger.warning("Document %s rejected in batch %s: %s", safe_fn, batch.batch_id, err_msg)
            continue

        existing_doc = batch_repo.find_document_by_hash(doc_hash)
        if existing_doc and existing_doc.document_id != doc_rec.document_id:
            doc_rec.status = DocumentStatus.DUPLICATE
            doc_rec.matched_document_id = existing_doc.document_id
            doc_rec.matched_batch_id = existing_doc.batch_id
            doc_rec.duplicate_reason = (
                f"Identical SHA-256 hash matches prior document '{existing_doc.document_id}' "
                f"in batch '{existing_doc.batch_id}'"
            )
            doc_rec.s3_key = existing_doc.s3_key
            batch.duplicate_count += 1
            batch_repo.save_document_record(doc_rec)
            processed_docs.append(doc_rec)
            logger.info("Duplicate document identified: %s matches %s (batch %s).", safe_fn, existing_doc.document_id, existing_doc.batch_id)
            continue

        try:
            if hasattr(doc_store, 'upload_batch_document'):
                s3_key = doc_store.upload_batch_document(
                    batch_id=batch.batch_id,
                    document_id=doc_rec.document_id,
                    filename=safe_fn,
                    data=data,
                    content_type=doc_rec.content_type,
                )
            else:
                s3_key = generate_batch_key(
                    batch_id=batch.batch_id,
                    document_id=doc_rec.document_id,
                    safe_filename=safe_fn,
                )
                doc_store.upload_document(
                    invoice_id=doc_rec.document_id,
                    filename=safe_fn,
                    data=data,
                    content_type=doc_rec.content_type,
                )
            doc_rec.s3_key = s3_key
            doc_rec.status = DocumentStatus.STORED

            batch_repo.save_document_hash_index(
                document_hash=doc_hash,
                document_id=doc_rec.document_id,
                batch_id=batch.batch_id,
                s3_key=s3_key,
            )

            bucket_name = getattr(doc_store, "bucket_name", "") or "ledgerguard-invoices"
            job = ProcessingJob(
                invoice_id=doc_rec.document_id,
                batch_id=batch.batch_id,
                document_id=doc_rec.document_id,
                s3_bucket=bucket_name,
                s3_key=s3_key,
                action="extract",
                idempotency_key=f"batch_{batch.batch_id}_{doc_rec.document_id}",
            )
            job_queue.send_job(job)

            doc_rec.status = DocumentStatus.QUEUED
            batch.accepted_count += 1
            batch.queued_count += 1
            logger.info("Successfully stored and queued document %s (%s) in batch %s.", doc_rec.document_id, safe_fn, batch.batch_id)
        except Exception as exc:
            logger.exception("Failed to store/queue document %s in batch %s: %s", doc_rec.document_id, batch.batch_id, exc)
            doc_rec.status = DocumentStatus.FAILED
            doc_rec.error_code = "INGESTION_FAILURE"
            doc_rec.error_message = f"Failed to persist or queue: {str(exc)}"
            batch.failed_count += 1
            batch.error_count += 1
        finally:
            batch_repo.save_document_record(doc_rec)
            processed_docs.append(doc_rec)

    batch.finalize_status()
    batch_repo.save_batch(batch)
    return _batch_to_response(batch, processed_docs)


@router.post(
    "/upload",
    response_model=BatchResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload and ingest files (auto-creates batch if not provided)",
)
async def upload_batch_documents_root(
    files: Annotated[list[UploadFile], File(...)],
    batch_id: Annotated[str | None, Form()] = None,
    source: Annotated[str, Form()] = "UI_UPLOAD",
    batch_repo: Annotated[BatchRepository, Depends(get_batch_repository)] = None,
    doc_store: Annotated[DocumentStore, Depends(get_document_store)] = None,
    job_queue: Annotated[JobQueue, Depends(get_job_queue)] = None,
    _auth: Annotated[str | None, Depends(require_api_key)] = None,
) -> BatchResponse:
    """Validate, store, deduplicate, and queue invoice documents under /batches/upload."""
    return await _process_batch_upload(
        files=files,
        batch_id=batch_id,
        source=source,
        batch_repo=batch_repo,
        doc_store=doc_store,
        job_queue=job_queue,
    )


@router.post(
    "/{batch_id}/upload",
    response_model=BatchResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload and ingest files into an existing batch",
)
async def upload_batch_documents_path(
    batch_id: str,
    files: Annotated[list[UploadFile], File(...)],
    source: Annotated[str, Form()] = "UI_UPLOAD",
    batch_repo: Annotated[BatchRepository, Depends(get_batch_repository)] = None,
    doc_store: Annotated[DocumentStore, Depends(get_document_store)] = None,
    job_queue: Annotated[JobQueue, Depends(get_job_queue)] = None,
    _auth: Annotated[str | None, Depends(require_api_key)] = None,
) -> BatchResponse:
    """Validate, store, deduplicate, and queue invoice documents under /batches/{batch_id}/upload."""
    return await _process_batch_upload(
        files=files,
        batch_id=batch_id,
        source=source,
        batch_repo=batch_repo,
        doc_store=doc_store,
        job_queue=job_queue,
    )


@router.get(
    "",
    response_model=BatchListResponse,
    summary="List bulk invoice ingestion batches",
)
def list_batches(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    batch_repo: Annotated[BatchRepository, Depends(get_batch_repository)] = None,
    _auth: Annotated[str | None, Depends(require_api_key)] = None,
) -> BatchListResponse:
    """Retrieve paginated list of batches sorted descending by creation time."""
    batches = batch_repo.list_batches(limit=limit, offset=offset)
    total = len(batches)
    return BatchListResponse(
        items=[_batch_to_response(b) for b in batches],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{batch_id}",
    response_model=BatchResponse,
    summary="Get details of a specific batch",
)
def get_batch(
    batch_id: str,
    batch_repo: Annotated[BatchRepository, Depends(get_batch_repository)],
    _auth: Annotated[str | None, Depends(require_api_key)] = None,
) -> BatchResponse:
    """Retrieve batch metadata along with all associated document records."""
    batch = batch_repo.get_batch(batch_id)
    if not batch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Batch '{batch_id}' not found.",
        )
    docs = batch_repo.list_batch_documents(batch_id)
    return _batch_to_response(batch, docs)


@router.get(
    "/{batch_id}/documents",
    response_model=BatchDocumentsResponse,
    summary="List documents within a batch",
)
def list_batch_documents(
    batch_id: str,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    status_filter: str | None = Query(default=None, alias="status"),
    batch_repo: Annotated[BatchRepository, Depends(get_batch_repository)] = None,
    _auth: Annotated[str | None, Depends(require_api_key)] = None,
) -> BatchDocumentsResponse:
    """Retrieve paginated document records belonging to the specified batch with optional status filtering."""
    batch = batch_repo.get_batch(batch_id)
    if not batch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Batch '{batch_id}' not found.",
        )
    if hasattr(batch_repo, "list_batch_documents_paginated"):
        docs, total = batch_repo.list_batch_documents_paginated(
            batch_id=batch_id,
            limit=limit,
            offset=offset,
            status=status_filter,
        )
    else:
        all_docs = batch_repo.list_batch_documents(batch_id)
        if status_filter:
            all_docs = [d for d in all_docs if (d.status.value if hasattr(d.status, "value") else d.status) == status_filter]
        total = len(all_docs)
        docs = all_docs[offset : offset + limit]

    return BatchDocumentsResponse(
        batch_id=batch_id,
        items=[_doc_to_response(d) for d in docs],
        total=total,
        limit=limit,
        offset=offset,
    )


# =============================================================================
# Phase 9: Fast O(1) Batch Progress & Resume Endpoints
# =============================================================================

@router.get(
    "/{batch_id}/progress",
    response_model=BatchProgressResponse,
    summary="Get O(1) operational progress summary for a batch",
)
def get_batch_progress(
    batch_id: str,
    batch_repo: Annotated[BatchRepository, Depends(get_batch_repository)],
    _auth: Annotated[str | None, Depends(require_api_key)] = None,
) -> BatchProgressResponse:
    """Return live progress, completion rate, throughput, and decision counts directly from BatchRecord."""
    batch = batch_repo.get_batch(batch_id)
    if not batch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Batch '{batch_id}' not found.",
        )

    # Calculate metrics
    now_dt = datetime.now(timezone.utc)
    elapsed_seconds = 0
    if batch.started_at:
        try:
            start_dt = datetime.fromisoformat(batch.started_at.replace("Z", "+00:00"))
            if batch.completed_at:
                end_dt = datetime.fromisoformat(batch.completed_at.replace("Z", "+00:00"))
                elapsed_seconds = max(1, int((end_dt - start_dt).total_seconds()))
            else:
                elapsed_seconds = max(1, int((now_dt - start_dt).total_seconds()))
        except Exception:
            elapsed_seconds = 1

    total_docs = batch.document_count
    completed_docs = batch.completed_count
    percent_complete = 0.0
    if total_docs > 0:
        percent_complete = round(min(100.0, (completed_docs / total_docs) * 100.0), 2)

    docs_per_minute = 0.0
    if elapsed_seconds > 0 and completed_docs > 0:
        docs_per_minute = round((completed_docs / elapsed_seconds) * 60.0, 2)

    return BatchProgressResponse(
        batch_id=batch.batch_id,
        status=batch.status.value,
        total_documents=total_docs,
        extracted_count=batch.extracted_count,
        queued_count=batch.queued_count,
        processing_count=batch.processing_count,
        completed_count=completed_docs,
        auto_approved_count=batch.auto_approved_count,
        manual_review_count=batch.manual_review_count,
        blocked_count=batch.blocked_count,
        duplicate_count=batch.duplicate_count,
        failed_count=batch.failed_count,
        percent_complete=percent_complete,
        documents_per_minute=docs_per_minute,
        elapsed_seconds=elapsed_seconds,
        retry_count=batch.retry_count,
    )


@router.post(
    "/{batch_id}/resume",
    response_model=BatchResumeResponse,
    summary="Resume processing for incomplete or retry-eligible documents in a batch",
)
def resume_batch(
    batch_id: str,
    batch_repo: Annotated[BatchRepository, Depends(get_batch_repository)],
    job_queue: Annotated[JobQueue, Depends(get_job_queue)],
    _auth: Annotated[str | None, Depends(require_api_key)] = None,
) -> BatchResumeResponse:
    """Re-enqueue only non-terminal or retry-eligible documents. Never reprocesses completed work."""
    batch = batch_repo.get_batch(batch_id)
    if not batch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Batch '{batch_id}' not found.",
        )

    all_docs = batch_repo.list_batch_documents(batch_id)
    terminal_statuses = {
        DocumentStatus.AUTO_APPROVED,
        DocumentStatus.MANUAL_REVIEW,
        DocumentStatus.BLOCKED,
        DocumentStatus.DUPLICATE,
    }

    resumed_count = 0
    now_iso = datetime.now(timezone.utc).isoformat()

    for doc in all_docs:
        # Strict Rule 10: Resume must NEVER reprocess terminal/completed documents
        if doc.status in terminal_statuses:
            continue

        # Retry eligibility check
        if doc.attempt_count >= doc.max_attempts:
            continue

        doc.attempt_count += 1
        doc.status = DocumentStatus.QUEUED
        doc.updated_at = now_iso
        doc.last_attempt_at = now_iso
        batch_repo.save_document_record(doc)

        job = ProcessingJob(
            batch_id=batch_id,
            document_id=doc.document_id,
            invoice_id=doc.document_id,
            s3_key=doc.s3_key,
            action="extract",
            attempt=doc.attempt_count,
        )
        job_queue.send_job(job)
        resumed_count += 1

    if resumed_count > 0:
        batch.status = BatchStatus.PROCESSING
        batch.updated_at = now_iso
        batch.last_progress_at = now_iso
        if not batch.started_at:
            batch.started_at = now_iso
        batch_repo.save_batch(batch)

    return BatchResumeResponse(
        batch_id=batch_id,
        resumed_count=resumed_count,
        status=batch.status.value,
        message=f"Successfully resumed {resumed_count} eligible documents in batch {batch_id}",
    )


# =============================================================================
# Phase 8: Autonomous PDF Understanding & Extraction Endpoints
# =============================================================================

@router.post(
    "/{batch_id}/documents/{document_id}/extract",
    response_model=ExtractionResponse,
    summary="Trigger on-demand extraction for a document",
)
def extract_document(
    batch_id: str,
    document_id: str,
    batch_repo: Annotated[BatchRepository, Depends(get_batch_repository)],
    doc_store: Annotated[DocumentStore, Depends(get_document_store)],
    job_queue: Annotated[JobQueue, Depends(get_job_queue)],
    _auth: Annotated[str | None, Depends(require_api_key)] = None,
) -> ExtractionResponse:
    """Autonomously extract structured invoice entities from raw PDF in S3."""
    doc = batch_repo.get_document_record(batch_id, document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document '{document_id}' not found in batch '{batch_id}'.",
        )
    if not doc.s3_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Document has no associated S3 storage key.",
        )

    try:
        pdf_bytes = doc_store.download_document(doc.s3_key)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to read document from storage: {str(exc)}",
        )

    doc.status = DocumentStatus.EXTRACTING
    doc.updated_at = datetime.now(timezone.utc).isoformat()
    batch_repo.save_document_record(doc)

    extractor = CompositeDocumentExtractor()
    res: ExtractionResult = extractor.extract(pdf_bytes, metadata={"document_id": document_id, "batch_id": batch_id})

    # Persist extraction result
    batch_repo.save_extraction_result(batch_id, document_id, res)

    # Update document record
    doc.extraction_status = res.status.value
    doc.overall_confidence = res.overall_confidence
    doc.extractor_provider = res.extractor_provider
    doc.extractor_version = res.extractor_version
    doc.extraction_summary = res.to_dynamodb_summary()

    if res.status == ExtractionStatus.FAILED:
        doc.status = DocumentStatus.EXTRACTION_FAILED
        doc.error_code = "EXTRACTION_FAILED"
        doc.error_message = "; ".join(res.errors) if res.errors else "Extraction failed"
    elif res.status in (ExtractionStatus.INSUFFICIENT_CONFIDENCE, ExtractionStatus.INSUFFICIENT_DATA) or res.overall_confidence < 0.85 or not res.reconstructed_invoice:
        doc.status = DocumentStatus.INSUFFICIENT_CONFIDENCE
    else:
        doc.status = DocumentStatus.EXTRACTION_VALIDATED
        if res.reconstructed_invoice:
            doc.extracted_invoice_id = res.reconstructed_invoice.invoice_id
            vendor_svc = VendorContextService()
            matched = vendor_svc.get_vendor(res.reconstructed_invoice.vendor_name)
            if matched:
                res.reconstructed_invoice.vendor_id = matched.vendor_id
                res.reconstructed_invoice.vendor_name = matched.legal_name
            else:
                res.reconstructed_invoice.vendor_id = "UNKNOWN_VENDOR"

            bucket_name = getattr(doc_store, "bucket_name", "") or "ledgerguard-invoices"
            job = ProcessingJob(
                invoice_id=res.reconstructed_invoice.invoice_id,
                batch_id=batch_id,
                document_id=document_id,
                s3_bucket=bucket_name,
                s3_key=doc.s3_key,
                action="extract",
                metadata={"source": "api_extraction"},
            )
            job_queue.send_job(job)

    doc.updated_at = datetime.now(timezone.utc).isoformat()
    batch_repo.save_document_record(doc)

    return ExtractionResponse(
        document_id=document_id,
        batch_id=batch_id,
        status=res.status.value,
        overall_confidence=res.overall_confidence,
        invoice_fields={k: f.to_summary_dict() for k, f in res.invoice_fields.items()},
        line_items=[li.to_summary_dict() for li in res.line_items],
        financials={k: f.to_summary_dict() for k, f in res.financials.items()},
        computed_subtotal=str(res.computed_subtotal) if res.computed_subtotal is not None else None,
        declared_total=str(res.declared_total) if res.declared_total is not None else None,
        computed_total=str(res.computed_total) if res.computed_total is not None else None,
        estimated_payable_amount=str(res.estimated_payable_amount) if res.estimated_payable_amount is not None else None,
        discrepancy=str(res.discrepancy) if res.discrepancy is not None else None,
        warnings=res.warnings,
        errors=res.errors,
        extracted_at=res.extracted_at,
        extractor_provider=res.extractor_provider,
        extractor_version=res.extractor_version,
        reconstructed_invoice_id=res.reconstructed_invoice.invoice_id if res.reconstructed_invoice else None,
    )


@router.get(
    "/{batch_id}/documents/{document_id}/extraction",
    response_model=ExtractionResponse,
    summary="Get stored extraction result and field confidence",
)
def get_document_extraction(
    batch_id: str,
    document_id: str,
    batch_repo: Annotated[BatchRepository, Depends(get_batch_repository)],
    _auth: Annotated[str | None, Depends(require_api_key)] = None,
) -> ExtractionResponse:
    """Retrieve structured extraction result and field confidence scores."""
    doc = batch_repo.get_document_record(batch_id, document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document '{document_id}' not found in batch '{batch_id}'.",
        )

    extraction_data = batch_repo.get_extraction_result(batch_id, document_id)
    if not extraction_data:
        if doc.extraction_summary:
            summary = doc.extraction_summary
            return ExtractionResponse(
                document_id=document_id,
                batch_id=batch_id,
                status=summary.get("status", doc.status.value),
                overall_confidence=float(summary.get("overall_confidence", doc.overall_confidence or 0.0)),
                invoice_fields={},
                line_items=[],
                financials={},
                computed_subtotal=summary.get("computed_subtotal"),
                declared_total=summary.get("declared_total"),
                computed_total=summary.get("computed_total"),
                estimated_payable_amount=summary.get("estimated_payable_amount"),
                discrepancy=summary.get("discrepancy"),
                warnings=summary.get("warnings", []),
                errors=summary.get("errors", []),
                extracted_at=summary.get("extracted_at", doc.updated_at),
                extractor_provider=summary.get("extractor_provider", "PdfTextExtractor"),
                extractor_version=summary.get("extractor_version", "1.0.0"),
                reconstructed_invoice_id=doc.extracted_invoice_id,
            )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Extraction result not found for document. Trigger extraction first.",
        )

    return ExtractionResponse(**extraction_data)


@router.post(
    "/{batch_id}/documents/{document_id}/correct",
    response_model=DocumentIngestionResponse,
    summary="Submit human AP corrections for extracted fields",
)
def correct_document_extraction(
    batch_id: str,
    document_id: str,
    request: DocumentCorrectionRequest,
    batch_repo: Annotated[BatchRepository, Depends(get_batch_repository)],
    inv_repo: Annotated[InvoiceRepository, Depends(get_invoice_repository)],
    job_queue: Annotated[JobQueue, Depends(get_job_queue)],
    _auth: Annotated[str | None, Depends(require_api_key)] = None,
) -> DocumentIngestionResponse:
    """Submit manual AP reviewer corrections to extracted invoice fields with full audit trail."""
    doc = batch_repo.get_document_record(batch_id, document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document '{document_id}' not found in batch '{batch_id}'.",
        )

    now_iso = datetime.now(timezone.utc).isoformat()

    for corr in request.corrections:
        old_val = (doc.extraction_summary or {}).get(corr.field_name, "UNSET")
        inv_repo.save_audit_event(
            AuditEvent(
                invoice_id=doc.extracted_invoice_id or document_id,
                event_type=AuditEventType.HUMAN_CORRECTION_RECORDED,
                details={
                    "field_name": corr.field_name,
                    "old_value": str(old_val),
                    "new_value": str(corr.new_value),
                    "reviewer_id": request.reviewer_id,
                    "reason": corr.reason or "Manual AP correction",
                    "timestamp": now_iso,
                },
            )
        )

    if not doc.extraction_summary:
        doc.extraction_summary = {}
    for corr in request.corrections:
        doc.extraction_summary[corr.field_name] = str(corr.new_value)

    doc.status = DocumentStatus.EXTRACTION_VALIDATED
    doc.updated_at = now_iso
    batch_repo.save_document_record(doc)

    if request.re_verify and doc.extracted_invoice_id:
        job = ProcessingJob(
            invoice_id=doc.extracted_invoice_id,
            batch_id=batch_id,
            document_id=document_id,
            action="verify",
            metadata={"source": "manual_correction", "reviewer": request.reviewer_id},
        )
        job_queue.send_job(job)

    return _doc_to_response(doc)


@router.post(
    "/{batch_id}/extract-all",
    response_model=dict[str, Any],
    summary="Trigger bulk extraction across all batch documents",
)
def extract_all_documents(
    batch_id: str,
    batch_repo: Annotated[BatchRepository, Depends(get_batch_repository)],
    job_queue: Annotated[JobQueue, Depends(get_job_queue)],
    _auth: Annotated[str | None, Depends(require_api_key)] = None,
) -> dict[str, Any]:
    """Queue autonomous extraction for all pending documents in the batch."""
    batch = batch_repo.get_batch(batch_id)
    if not batch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Batch '{batch_id}' not found.",
        )

    docs = batch_repo.list_batch_documents(batch_id)
    eligible_docs = [
        d for d in docs if d.status in (DocumentStatus.STORED, DocumentStatus.QUEUED, DocumentStatus.AWAITING_EXTRACTION)
    ]

    queued_count = 0
    for doc in eligible_docs:
        job = ProcessingJob(
            invoice_id=doc.document_id,
            batch_id=batch_id,
            document_id=doc.document_id,
            s3_key=doc.s3_key,
            action="extract",
            metadata={"source": "bulk_extract_all"},
        )
        job_queue.send_job(job)
        doc.status = DocumentStatus.QUEUED
        batch_repo.save_document_record(doc)
        queued_count += 1

    batch.status = BatchStatus.PROCESSING
    batch.updated_at = datetime.now(timezone.utc).isoformat()
    batch_repo.save_batch(batch)

    return {
        "batch_id": batch_id,
        "total_documents": len(docs),
        "queued_for_extraction": queued_count,
        "status": "EXTRACTION_DISPATCHED",
    }
