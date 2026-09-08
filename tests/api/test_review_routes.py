"""Offline unit tests for human review workflow routes and safety guarantees."""

from app.models.decision import AgentDecision
from app.models.persistence import InvoiceRecord
from app.services.state import ProcessingState


def test_submit_human_review_approve_success(client, mock_repo, auth_headers):
    """Auditor approval on MANUAL_REVIEW invoice records reviewer details without erasing automated decision."""
    record = InvoiceRecord(
        invoice_id="INV-REV-01",
        invoice_number="NUM-REV-01",
        vendor_id="VEND-01",
        vendor_name="Vendor 1",
        invoice_date="2026-03-01",
        processing_status=ProcessingState.MANUAL_REVIEW,
        decision=AgentDecision.MANUAL_REVIEW,
    )
    mock_repo.save_record(record)

    payload = {
        "reviewer": "auditor_jane",
        "action": "APPROVE",
        "comment": "Verified vendor bank account via dual authorization.",
    }

    response = client.post("/invoices/INV-REV-01/review", json=payload, headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["invoice_id"] == "INV-REV-01"
    assert data["original_decision"] == "MANUAL_REVIEW"
    assert data["review_decision"] == "APPROVE"
    assert data["reviewer"] == "auditor_jane"
    assert "dual authorization" in data["review_comment"]

    # Verify repository record persistence
    updated = mock_repo.get_record("INV-REV-01")
    assert updated.original_decision == AgentDecision.MANUAL_REVIEW
    assert updated.review_decision == "APPROVE"
    assert updated.reviewer == "auditor_jane"

    # Verify append-only audit event emitted
    events = mock_repo.get_audit_events("INV-REV-01")
    review_events = [e for e in events if e.event_type == "HUMAN_REVIEW_RECORDED"]
    assert len(review_events) == 1
    assert review_events[0].details["reviewer"] == "auditor_jane"
    assert review_events[0].details["action"] == "APPROVE"


def test_submit_human_review_on_processing_conflict(client, mock_repo, auth_headers):
    """Attempting review while invoice is still PROCESSING returns 409 Conflict."""
    record = InvoiceRecord(
        invoice_id="INV-REV-PROC",
        invoice_number="NUM-01",
        vendor_id="VEND-01",
        vendor_name="Vendor 1",
        invoice_date="2026-03-01",
        processing_status=ProcessingState.PROCESSING,
    )
    mock_repo.save_record(record)

    payload = {
        "reviewer": "auditor_jane",
        "action": "APPROVE",
        "comment": "Attempt premature review",
    }
    response = client.post("/invoices/INV-REV-PROC/review", json=payload, headers=auth_headers)
    assert response.status_code == 409
    assert response.json()["error"] == "CONFLICT"


def test_submit_human_review_on_blocked_conflict(client, mock_repo, auth_headers):
    """Attempting review on a BLOCKED invoice returns 409 Conflict (safety guard cannot be bypassed)."""
    record = InvoiceRecord(
        invoice_id="INV-REV-BLOCK",
        invoice_number="NUM-01",
        vendor_id="VEND-01",
        vendor_name="Vendor 1",
        invoice_date="2026-03-01",
        processing_status=ProcessingState.BLOCKED,
        decision=AgentDecision.BLOCK,
    )
    mock_repo.save_record(record)

    payload = {
        "reviewer": "auditor_jane",
        "action": "APPROVE",
        "comment": "Try to force approve blocked invoice",
    }
    response = client.post("/invoices/INV-REV-BLOCK/review", json=payload, headers=auth_headers)
    assert response.status_code == 409
    assert response.json()["error"] == "CONFLICT"
    assert "BLOCKED" in response.json()["message"]


def test_submit_human_review_not_found(client, auth_headers):
    """Reviewing a nonexistent invoice returns 404."""
    payload = {
        "reviewer": "auditor_jane",
        "action": "APPROVE",
        "comment": "Review missing invoice",
    }
    response = client.post("/invoices/INV-MISSING/review", json=payload, headers=auth_headers)
    assert response.status_code == 404
    assert response.json()["error"] == "INVOICE_NOT_FOUND"


def test_submit_human_review_invalid_action(client, auth_headers):
    """Review action must be one of APPROVE, REJECT, REQUEST_INFORMATION."""
    payload = {
        "reviewer": "auditor_jane",
        "action": "IGNORE_RISK",  # Invalid action
        "comment": "Invalid action attempt",
    }
    response = client.post("/invoices/INV-01/review", json=payload, headers=auth_headers)
    assert response.status_code == 422
