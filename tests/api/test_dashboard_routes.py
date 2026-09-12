"""Unit tests for GET /dashboard/stats route."""

from decimal import Decimal
from fastapi.testclient import TestClient

from app.models.decision import AgentDecision
from app.models.verification import RiskLevel
from app.models.persistence import InvoiceRecord
from app.services.state import ProcessingState


def test_get_dashboard_stats_empty(client: TestClient, auth_headers: dict[str, str]):
    """Empty repository returns zeroed metrics."""
    response = client.get("/dashboard/stats", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total_invoices"] == 0
    assert data["pending_invoices"] == 0
    assert data["processed_invoices"] == 0
    assert data["auto_approved_count"] == 0
    assert data["manual_review_count"] == 0
    assert data["blocked_count"] == 0
    assert data["total_amount_usd"] == 0.0
    assert data["average_risk_score"] == 0.0
    assert data["auto_approval_rate_pct"] == 0.0


def test_get_dashboard_stats_aggregated(client: TestClient, mock_repo, auth_headers: dict[str, str]):
    """Populated repository aggregates metrics, rates, and amounts correctly."""
    r1 = InvoiceRecord(
        invoice_id="INV-001",
        invoice_number="INV-001",
        vendor_id="VEND-A",
        vendor_name="Vendor Alpha",
        invoice_date="2026-03-01",
        total=Decimal("100.00"),
        processing_status=ProcessingState.AUTO_APPROVED,
        decision=AgentDecision.AUTO_APPROVE,
        risk_level=RiskLevel.LOW,
        risk_score=10,
    )
    r2 = InvoiceRecord(
        invoice_id="INV-002",
        invoice_number="INV-002",
        vendor_id="VEND-B",
        vendor_name="Vendor Beta",
        invoice_date="2026-03-02",
        total=Decimal("500.00"),
        processing_status=ProcessingState.MANUAL_REVIEW,
        decision=AgentDecision.MANUAL_REVIEW,
        risk_level=RiskLevel.MEDIUM,
        risk_score=45,
    )
    r3 = InvoiceRecord(
        invoice_id="INV-003",
        invoice_number="INV-003",
        vendor_id="VEND-C",
        vendor_name="Vendor Gamma",
        invoice_date="2026-03-03",
        total=Decimal("1000.00"),
        processing_status=ProcessingState.BLOCKED,
        decision=AgentDecision.BLOCK,
        risk_level=RiskLevel.CRITICAL,
        risk_score=95,
    )
    r4 = InvoiceRecord(
        invoice_id="INV-004",
        invoice_number="INV-004",
        vendor_id="VEND-D",
        vendor_name="Vendor Delta",
        invoice_date="2026-03-04",
        total=Decimal("250.00"),
        processing_status=ProcessingState.PROCESSING,
    )
    for r in (r1, r2, r3, r4):
        mock_repo.save_record(r)

    response = client.get("/dashboard/stats", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total_invoices"] == 4
    assert data["processed_invoices"] == 3
    assert data["pending_invoices"] == 1
    assert data["auto_approved_count"] == 1
    assert data["manual_review_count"] == 1
    assert data["blocked_count"] == 1
    assert data["total_amount_usd"] == 1850.0
    # Average of 10, 45, 95 = 150 / 3 = 50.0
    assert data["average_risk_score"] == 50.0
    # 1 auto-approved out of 3 processed = 33.3%
    assert data["auto_approval_rate_pct"] == 33.3
    assert data["by_decision"]["AUTO_APPROVE"] == 1
    assert data["by_decision"]["MANUAL_REVIEW"] == 1
    assert data["by_decision"]["BLOCK"] == 1


def test_dashboard_stats_requires_auth(client: TestClient):
    """Missing or invalid API key returns 401."""
    res_no_key = client.get("/dashboard/stats")
    assert res_no_key.status_code == 401

    res_bad_key = client.get("/dashboard/stats", headers={"X-API-Key": "invalid-key"})
    assert res_bad_key.status_code == 401
