"""Comprehensive test suite for LedgerGuard Phase 8: Autonomous PDF Understanding & Structured Extraction.

Validates:
1. Real invoice test set (SuperStore 36259, Apex 33527, Nova 8673)
2. 10 Synthetic extraction scenarios (clean, discount, shipping, tax, combined, missing total,
   missing vendor, unreadable, arithmetic mismatch, duplicate)
3. Strict Decimal precision (zero float tolerance)
4. NOT_STATED field preservation (no 0.00 fabrication)
5. Declared vs computed arithmetic comparison
6. Vendor Master resolution and linking
7. Worker pipeline integration and Decision Guard verdict
8. Human correction and audit trail recording
9. REST API extraction endpoints
"""

from datetime import date
from decimal import Decimal
import os
import pytest
from unittest.mock import MagicMock

from app.agent.orchestrator import run_verification_workflow
from app.api.dependencies import get_batch_repository, get_document_store, get_job_queue
from app.api.main import app
from app.models.audit import AuditEvent, AuditEventType
from app.models.batch import BatchRecord, BatchStatus, DocumentIngestionRecord, DocumentStatus
from app.models.decision import AgentDecision
from app.models.extraction import (
    ExtractionField,
    ExtractionResult,
    ExtractionStatus,
    FieldStatus,
)
from app.models.invoice import Invoice, LineItem
from app.models.job import ProcessingJob
from app.models.persistence import InvoiceRecord
from app.models.policy import PolicyConfig
from app.models.state import ProcessingState
from app.services.document_extraction import (
    CompositeDocumentExtractor,
    MockDocumentExtractor,
    PdfTextExtractor,
)
from app.services.interfaces import BatchRepository, DocumentStore, InvoiceRepository, JobQueue
from app.services.vendor_context import VendorContextService
from app.worker.processor import InvoiceProcessor
from tests.test_batch_ingestion import InMemoryBatchRepository, InMemoryDocumentStore, InMemoryJobQueue
from starlette.testclient import TestClient

FIXTURE_DIR = "tests/fixtures/synthetic_invoices"


def read_fixture(filename: str) -> bytes:
    path = os.path.join(FIXTURE_DIR, filename)
    with open(path, "rb") as f:
        return f.read()


# =============================================================================
# 1. Real Invoices Extraction Tests (Step 28)
# =============================================================================

def test_extract_superstore_invoice_36259():
    """Verify exact extraction for real SuperStore #36259 invoice.

    - Invoice Number: 36259
    - Vendor: SuperStore
    - Date: 2012-03-06
    - Line item: Newell 330, Qty: 3, Rate: 17.94, Amount: 53.82
    - Subtotal: 53.82, Shipping: 4.29, Total: 58.11
    - Tax: NOT_STATED (value is None, NOT fabricated as 0.00)
    """
    pdf_bytes = read_fixture("INV-SUPERSTORE-36259.pdf")
    extractor = PdfTextExtractor()
    result = extractor.extract(pdf_bytes, metadata={"document_id": "doc_superstore_36259"})

    assert result.status in (ExtractionStatus.SUCCESS, ExtractionStatus.PARTIAL)
    assert result.overall_confidence >= 0.85

    # Field Assertions
    inv_num_field = result.invoice_fields["invoice_number"]
    assert inv_num_field.value == "36259"
    assert inv_num_field.confidence >= 0.90
    assert inv_num_field.source_page == 1

    vendor_field = result.invoice_fields["vendor_name"]
    assert vendor_field.value == "SuperStore"
    assert vendor_field.confidence >= 0.90

    date_field = result.invoice_fields["invoice_date"]
    assert date_field.value == date(2012, 3, 6)

    # Line Item Assertions
    assert len(result.line_items) == 1
    li = result.line_items[0]
    assert "Newell 330" in str(li.description.value)
    assert li.quantity.value == Decimal("3.00") or li.quantity.value == Decimal("3")
    assert li.unit_price.value == Decimal("17.94")
    assert li.amount.value == Decimal("53.82")

    # Financial Assertions
    assert result.financials["subtotal"].value == Decimal("53.82")
    assert result.financials["shipping"].value == Decimal("4.29")
    assert result.financials["total"].value == Decimal("58.11")

    # Tax NOT_STATED rule: must NOT fabricate 0.00
    tax_field = result.financials["tax"]
    assert tax_field.status == FieldStatus.NOT_STATED
    assert tax_field.value is None

    # Declared vs Computed total check
    assert result.declared_total == Decimal("58.11")
    assert result.computed_total == Decimal("58.11")
    assert result.discrepancy == Decimal("0.00")

    # Reconstructed canonical invoice
    canon = result.reconstructed_invoice
    assert canon is not None
    assert canon.invoice_number == "36259"
    assert canon.subtotal == Decimal("53.82")
    assert canon.shipping == Decimal("4.29")
    assert canon.total == Decimal("58.11")
    assert canon.tax is None  # Strictly None, never 0.00


def test_superstore_reconstructed_invoice_verification():
    """Verify that reconstructed SuperStore invoice runs through full verification pipeline.

    Expected result is AUTO_APPROVE only if all vendor, duplicate, policy, risk, arithmetic,
    and Decision Guard checks pass.
    """
    pdf_bytes = read_fixture("INV-SUPERSTORE-36259.pdf")
    extractor = PdfTextExtractor()
    result = extractor.extract(pdf_bytes, metadata={"document_id": "doc_superstore_36259"})
    invoice = result.reconstructed_invoice
    assert invoice is not None

    vendor_svc = VendorContextService()
    vendor = vendor_svc.get_vendor(invoice.vendor_name)
    assert vendor is not None
    assert vendor.vendor_id == "SUPERSTORE-001"
    invoice.vendor_id = vendor.vendor_id
    invoice.vendor_name = vendor.legal_name

    history_inv = Invoice(
        invoice_id="INV-SUPERSTORE-PRIOR",
        invoice_number="36000",
        vendor_id="SUPERSTORE-001",
        vendor_name="SuperStore",
        customer_name="Global Enterprise Org",
        invoice_date=date(2012, 1, 15),
        subtotal=Decimal("50.00"),
        shipping=Decimal("5.00"),
        total=Decimal("55.00"),
    )

    decision, meta = run_verification_workflow(
        invoice=invoice,
        history=[history_inv],
    )

    assert decision.decision == AgentDecision.AUTO_APPROVE
    assert not meta.was_overridden


def test_extract_apex_invoice_33527():
    """Verify extraction for Apex Solutions invoice."""
    pdf_bytes = read_fixture("INV-APEX-33527.pdf")
    result = PdfTextExtractor().extract(pdf_bytes, metadata={"document_id": "doc_apex_33527"})

    assert result.invoice_fields["invoice_number"].value == "33527"
    assert result.invoice_fields["vendor_name"].value == "Apex Solutions"
    assert result.financials["subtotal"].value == Decimal("1500.00")
    assert result.financials["tax"].value == Decimal("120.00")
    assert result.financials["total"].value == Decimal("1620.00")
    assert result.discrepancy == Decimal("0.00")


def test_extract_nova_invoice_8673():
    """Verify extraction for Nova Advisory invoice with discount."""
    pdf_bytes = read_fixture("INV-NOVA-8673.pdf")
    result = PdfTextExtractor().extract(pdf_bytes, metadata={"document_id": "doc_nova_8673"})

    assert result.invoice_fields["invoice_number"].value == "8673"
    assert result.invoice_fields["vendor_name"].value == "Nova Advisory Partners"
    assert result.financials["subtotal"].value == Decimal("3200.00")
    assert result.financials["discount"].value == Decimal("200.00")
    assert result.financials["total"].value == Decimal("3000.00")


# =============================================================================
# 2. Synthetic Test Set (10 Scenarios) (Step 29)
# =============================================================================

def test_synthetic_1_clean_invoice():
    pdf_bytes = read_fixture("clean_invoice.pdf")
    res = PdfTextExtractor().extract(pdf_bytes, metadata={"document_id": "syn_clean"})
    assert res.status in (ExtractionStatus.SUCCESS, ExtractionStatus.PARTIAL)
    assert res.invoice_fields["invoice_number"].value == "INV-CLEAN-01"
    assert res.financials["total"].value == Decimal("250.00")


def test_synthetic_2_discount_invoice():
    pdf_bytes = read_fixture("discount_invoice.pdf")
    res = PdfTextExtractor().extract(pdf_bytes, metadata={"document_id": "syn_disc"})
    assert res.financials["discount"].value == Decimal("50.00")
    assert res.financials["total"].value == Decimal("350.00")
    assert res.computed_total == Decimal("350.00")


def test_synthetic_3_shipping_invoice():
    pdf_bytes = read_fixture("shipping_invoice.pdf")
    res = PdfTextExtractor().extract(pdf_bytes, metadata={"document_id": "syn_ship"})
    assert res.financials["shipping"].value == Decimal("45.00")
    assert res.financials["total"].value == Decimal("345.00")


def test_synthetic_4_tax_invoice():
    pdf_bytes = read_fixture("tax_invoice.pdf")
    res = PdfTextExtractor().extract(pdf_bytes, metadata={"document_id": "syn_tax"})
    assert res.financials["tax"].value == Decimal("80.00")
    assert res.financials["total"].value == Decimal("1080.00")


def test_synthetic_5_combined_discount_shipping_tax():
    pdf_bytes = read_fixture("combined_discount_shipping_tax.pdf")
    res = PdfTextExtractor().extract(pdf_bytes, metadata={"document_id": "syn_comb"})
    assert len(res.line_items) == 2
    assert res.financials["subtotal"].value == Decimal("350.00")
    assert res.financials["discount"].value == Decimal("30.00")
    assert res.financials["shipping"].value == Decimal("25.00")
    assert res.financials["tax"].value == Decimal("27.60")
    assert res.financials["total"].value == Decimal("372.60")
    assert res.discrepancy == Decimal("0.00")


def test_synthetic_6_missing_total():
    pdf_bytes = read_fixture("missing_total.pdf")
    res = PdfTextExtractor().extract(pdf_bytes, metadata={"document_id": "syn_notot"})
    assert res.status == ExtractionStatus.INSUFFICIENT_DATA
    assert res.financials["total"].status == FieldStatus.NOT_STATED
    assert res.financials["total"].value is None


def test_synthetic_7_missing_vendor():
    pdf_bytes = read_fixture("missing_vendor.pdf")
    res = PdfTextExtractor().extract(pdf_bytes, metadata={"document_id": "syn_novend"})
    assert res.status == ExtractionStatus.INSUFFICIENT_DATA
    assert res.invoice_fields["vendor_name"].status == FieldStatus.NOT_STATED


def test_synthetic_8_unreadable_invoice():
    pdf_bytes = read_fixture("unreadable_invoice.pdf")
    res = PdfTextExtractor().extract(pdf_bytes, metadata={"document_id": "syn_unreadable"})
    assert res.status == ExtractionStatus.FAILED
    assert res.overall_confidence == 0.0
    assert len(res.errors) > 0


def test_synthetic_9_arithmetic_mismatch():
    pdf_bytes = read_fixture("arithmetic_mismatch.pdf")
    res = PdfTextExtractor().extract(pdf_bytes, metadata={"document_id": "syn_mismatch"})
    assert res.declared_total == Decimal("150.00")
    assert res.computed_total == Decimal("120.00")
    assert res.discrepancy == Decimal("30.00")
    assert any("ARITHMETIC_MISMATCH" in w for w in res.warnings)


def test_synthetic_10_duplicate_document():
    clean_bytes = read_fixture("clean_invoice.pdf")
    dup_bytes = read_fixture("duplicate_document.pdf")
    from app.services.batch_validator import compute_sha256
    assert compute_sha256(clean_bytes) == compute_sha256(dup_bytes)


# =============================================================================
# 3. Decimal Normalization & Strict Precision Tests (Step 9)
# =============================================================================

def test_decimal_normalization_rejects_float():
    with pytest.raises(TypeError, match="Floating-point values are strictly forbidden"):
        ExtractionField(field_name="total", value=58.11)

    with pytest.raises(TypeError, match="Floating-point values are strictly forbidden"):
        ExtractionResult(
            document_id="doc_test",
            status=ExtractionStatus.SUCCESS,
            declared_total=100.50,
        )


def test_decimal_string_normalization():
    from app.services.document_extraction import _parse_decimal
    assert _parse_decimal("$1,234.56") == Decimal("1234.56")
    assert _parse_decimal("€ 53.82") == Decimal("53.82")
    assert _parse_decimal("£ 999.00") == Decimal("999.00")
    assert _parse_decimal("120") == Decimal("120.00")
    assert _parse_decimal(None) is None
    assert _parse_decimal("") is None


# =============================================================================
# 4. Worker Integration & Autonomous Pipeline Tests (Step 19)
# =============================================================================

def test_worker_phase8_autonomous_extraction():
    doc_store = InMemoryDocumentStore()
    repo = MagicMock()
    repo.get_record.return_value = None
    repo.get_document_record.return_value = DocumentIngestionRecord(
        document_id="doc_36259",
        batch_id="LG-BATCH-36259",
        original_filename="INV-SUPERSTORE-36259.pdf",
        safe_filename="INV-SUPERSTORE-36259.pdf",
        document_hash="dummy_hash",
        s3_key="batches/LG-BATCH-36259/documents/doc_36259/INV-SUPERSTORE-36259.pdf",
        status=DocumentStatus.AWAITING_EXTRACTION,
    )
    repo.get_batch.return_value = BatchRecord(batch_id="LG-BATCH-36259")
    queue = InMemoryJobQueue()

    s3_key = "batches/LG-BATCH-36259/documents/doc_36259/INV-SUPERSTORE-36259.pdf"
    doc_store.files[s3_key] = read_fixture("INV-SUPERSTORE-36259.pdf")

    processor = InvoiceProcessor(
        document_store=doc_store,
        repository=repo,
        job_queue=queue,
        extractor=PdfTextExtractor(),
    )

    job = ProcessingJob(
        invoice_id="doc_36259",
        batch_id="LG-BATCH-36259",
        document_id="doc_36259",
        s3_key=s3_key,
        action="extract",
    )

    success = processor.process_job(job, receipt_handle="receipt_ack_1")
    assert success is True
    assert "receipt_ack_1" in queue.acked_jobs

    repo.save_audit_event.assert_called()
    event_types = [call[0][0].event_type for call in repo.save_audit_event.call_args_list]
    assert AuditEventType.EXTRACTION_STARTED in event_types
    assert AuditEventType.EXTRACTION_VALIDATED in event_types


def test_worker_phase8_low_confidence_routes_to_manual_review():
    doc_store = InMemoryDocumentStore()
    repo = MagicMock()
    repo.get_record.return_value = None
    repo.get_document_record.return_value = DocumentIngestionRecord(
        document_id="doc_low_conf",
        batch_id="LG-BATCH-LOW",
        original_filename="missing_total.pdf",
        safe_filename="missing_total.pdf",
        document_hash="dummy_hash",
        s3_key="batches/LG-BATCH-LOW/doc_low_conf/missing_total.pdf",
        status=DocumentStatus.AWAITING_EXTRACTION,
    )
    repo.get_batch.return_value = BatchRecord(batch_id="LG-BATCH-LOW")
    queue = InMemoryJobQueue()

    s3_key = "batches/LG-BATCH-LOW/doc_low_conf/missing_total.pdf"
    doc_store.files[s3_key] = read_fixture("missing_total.pdf")

    processor = InvoiceProcessor(
        document_store=doc_store,
        repository=repo,
        job_queue=queue,
        extractor=PdfTextExtractor(),
    )

    job = ProcessingJob(
        invoice_id="doc_low_conf",
        batch_id="LG-BATCH-LOW",
        document_id="doc_low_conf",
        s3_key=s3_key,
        action="extract",
    )

    success = processor.process_job(job, receipt_handle="receipt_ack_low")
    assert success is True
    assert "receipt_ack_low" in queue.acked_jobs

    saved_doc = repo.save_document_record.call_args[0][0]
    assert saved_doc.status in (DocumentStatus.INSUFFICIENT_CONFIDENCE, DocumentStatus.INSUFFICIENT_DATA)


# =============================================================================
# 5. REST API Extraction & Correction Endpoints Tests (Steps 22-24)
# =============================================================================

def test_api_extract_and_correct_document():
    batch_repo = InMemoryBatchRepository()
    doc_store = InMemoryDocumentStore()
    job_queue = InMemoryJobQueue()

    app.dependency_overrides[get_batch_repository] = lambda: batch_repo
    app.dependency_overrides[get_document_store] = lambda: doc_store
    app.dependency_overrides[get_job_queue] = lambda: job_queue

    client = TestClient(app)

    pdf_bytes = read_fixture("INV-SUPERSTORE-36259.pdf")
    upload_resp = client.post(
        "/batches/upload",
        files=[("files", ("INV-SUPERSTORE-36259.pdf", pdf_bytes, "application/pdf"))],
    )
    assert upload_resp.status_code == 201
    batch_data = upload_resp.json()
    batch_id = batch_data["batch_id"]
    doc_id = batch_data["documents"][0]["document_id"]

    ext_resp = client.post(f"/batches/{batch_id}/documents/{doc_id}/extract")
    assert ext_resp.status_code == 200
    ext_data = ext_resp.json()
    assert ext_data["status"] in ("SUCCESS", "PARTIAL")
    assert ext_data["invoice_fields"]["invoice_number"]["value"] == "36259"
    assert ext_data["financials"]["total"]["value"] == "58.11"

    get_ext_resp = client.get(f"/batches/{batch_id}/documents/{doc_id}/extraction")
    assert get_ext_resp.status_code == 200
    assert get_ext_resp.json()["document_id"] == doc_id

    corr_payload = {
        "reviewer_id": "senior_auditor_alice",
        "corrections": [
            {"field_name": "tax", "new_value": "0.00", "reason": "Verified tax exempt on source PO"},
        ],
        "re_verify": True,
    }
    corr_resp = client.post(f"/batches/{batch_id}/documents/{doc_id}/correct", json=corr_payload)
    assert corr_resp.status_code == 200
    updated_doc = corr_resp.json()
    assert updated_doc["status"] == DocumentStatus.EXTRACTION_VALIDATED.value
    assert updated_doc["extraction_summary"]["tax"] == "0.00"

    bulk_resp = client.post(f"/batches/{batch_id}/extract-all")
    assert bulk_resp.status_code == 200
    assert bulk_resp.json()["status"] == "EXTRACTION_DISPATCHED"

    app.dependency_overrides.clear()
