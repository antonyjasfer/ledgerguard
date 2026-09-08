"""Offline unit tests for invoice status querying routes."""

from decimal import Decimal

from app.models.decision import AgentDecision
from app.models.persistence import InvoiceRecord
from app.models.verification import RiskLevel
from app.services.state import ProcessingState


def test_get_invoice_status_success(client, mock_repo, auth_headers):
    """Querying an existing invoice status returns complete verified record."""
    record = InvoiceRecord(
        invoice_id="INV-STAT-01",
        invoice_number="ACME-STAT",
        vendor_id="VEND-01",
        vendor_name="Acme Supplies",
        invoice_date="2026-03-01",
        currency="USD",
        total=Decimal("500.00"),
        processing_status=ProcessingState.AUTO_APPROVED,
        decision=AgentDecision.AUTO_APPROVE,
        risk_level=RiskLevel.LOW,
        risk_score=10,
        agent_run_id="run_test_123",
        verification_summary={"status": "clean"},
    )
    mock_repo.save_record(record)

    response = client.get("/invoices/INV-STAT-01", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["invoice_id"] == "INV-STAT-01"
    assert data["processing_status"] == "AUTO_APPROVED"
    assert data["decision"] == "AUTO_APPROVE"
    assert data["risk_level"] == "LOW"
    assert data["risk_score"] == 10
    assert data["agent_run_id"] == "run_test_123"

    # Verify no private AWS fields are present
    assert "AWS_SECRET_ACCESS_KEY" not in str(data)
    assert "credentials" not in str(data)


def test_get_invoice_status_not_found(client, auth_headers):
    """Querying a missing invoice returns 404 Not Found."""
    response = client.get("/invoices/INV-NONEXISTENT", headers=auth_headers)
    assert response.status_code == 404
    assert response.json()["error"] == "INVOICE_NOT_FOUND"
