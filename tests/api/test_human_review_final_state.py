"""Tests for Human Review Final Status and Dashboard Visibility (Steps 14, 15, 16)."""

from decimal import Decimal
from app.models.decision import AgentDecision
from app.models.persistence import InvoiceRecord
from app.services.state import ProcessingState, FinalState, derive_final_state


def test_human_review_approve_exact_bug(client, mock_repo, auth_headers):
    """
    STEP 14 — TEST THE EXACT BUG:
    Invoice with automated_decision = MANUAL_REVIEW.
    Perform Human Review -> APPROVE.
    Verify:
    1. GET /invoices/{id} returns:
       automated_decision = MANUAL_REVIEW
       human_review_decision = APPROVE
       final_state = HUMAN_APPROVED
    2. list_records:
       final_state = HUMAN_APPROVED
       filter status=HUMAN_APPROVED finds it
       filter status=MANUAL_REVIEW does NOT find it (disappears from active MANUAL_REVIEW)
    3. Dashboard:
       manual_review_count does NOT count it
       human_approved_count counts it
       human_approved_value includes its total
       manual_review_value does NOT include its total
    """
    record = InvoiceRecord(
        invoice_id="INV-BUG-APPROVAL",
        invoice_number="BUG-001",
        vendor_id="VEND-01",
        vendor_name="Acme Supplies",
        invoice_date="2026-03-01",
        total=Decimal("1250.00"),
        subtotal=Decimal("1200.00"),
        tax=Decimal("50.00"),
        processing_status=ProcessingState.MANUAL_REVIEW,
        decision=AgentDecision.MANUAL_REVIEW,
    )
    mock_repo.save_record(record)

    # Pre-review dashboard check
    stats_pre = client.get("/dashboard/stats", headers=auth_headers).json()
    pre_manual_count = stats_pre["manual_review_count"]
    pre_manual_val = Decimal(stats_pre["manual_review_value"])
    pre_human_app_count = stats_pre.get("human_approved_count", 0)

    # Perform Human Review -> APPROVE
    payload = {
        "reviewer": "auditor_elena",
        "action": "APPROVE",
        "comment": "Approved after manual document verification.",
    }
    rev_resp = client.post("/invoices/INV-BUG-APPROVAL/review", json=payload, headers=auth_headers)
    assert rev_resp.status_code == 200
    rev_data = rev_resp.json()
    assert rev_data["original_decision"] == "MANUAL_REVIEW"
    assert rev_data["automated_decision"] == "MANUAL_REVIEW"
    assert rev_data["review_decision"] == "APPROVE"
    assert rev_data["human_review_decision"] == "APPROVE"
    assert rev_data["final_state"] == "HUMAN_APPROVED"

    # 1. Verify GET /invoices/{id}
    detail_resp = client.get("/invoices/INV-BUG-APPROVAL", headers=auth_headers)
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert detail["automated_decision"] == "MANUAL_REVIEW"
    assert detail["human_review_decision"] == "APPROVE"
    assert detail["final_state"] == "HUMAN_APPROVED"
    assert detail["human_review_reviewer"] == "auditor_elena"
    assert detail["human_review_comment"] == "Approved after manual document verification."

    # 2. Verify Invoice Listing and Filter Behavior (STEP 10)
    list_all = client.get("/invoices", headers=auth_headers).json()
    inv_item = next(item for item in list_all["items"] if item["invoice_id"] == "INV-BUG-APPROVAL")
    assert inv_item["final_state"] == "HUMAN_APPROVED"
    assert inv_item["automated_decision"] == "MANUAL_REVIEW"
    assert inv_item["human_review_decision"] == "APPROVE"

    # Filter by HUMAN_APPROVED: must find it
    list_approved = client.get("/invoices?status=HUMAN_APPROVED", headers=auth_headers).json()
    assert any(item["invoice_id"] == "INV-BUG-APPROVAL" for item in list_approved["items"])

    # Filter by MANUAL_REVIEW: must NOT find it (it is no longer awaiting human action)
    list_manual = client.get("/invoices?status=MANUAL_REVIEW", headers=auth_headers).json()
    assert not any(item["invoice_id"] == "INV-BUG-APPROVAL" for item in list_manual["items"])

    # 3. Verify Dashboard Aggregations (STEPS 7, 8, 9, 12)
    stats_post = client.get("/dashboard/stats", headers=auth_headers).json()
    assert stats_post["manual_review_count"] == pre_manual_count - 1
    assert stats_post["human_approved_count"] == pre_human_app_count + 1
    assert Decimal(stats_post["human_approved_value"]) >= Decimal("1250.00")
    assert Decimal(stats_post["manual_review_value"]) == pre_manual_val - Decimal("1250.00")


def test_human_review_reject(client, mock_repo, auth_headers):
    """
    STEP 15 — TEST REJECTION:
    Invoice with automated_decision = MANUAL_REVIEW.
    Human Review -> REJECT.
    Verify:
    1. final_state = HUMAN_REJECTED
    2. disappears from active MANUAL REVIEW
    3. appears in HUMAN REJECTED
    """
    record = InvoiceRecord(
        invoice_id="INV-BUG-REJECT",
        invoice_number="BUG-002",
        vendor_id="VEND-02",
        vendor_name="Shady Parts Ltd",
        invoice_date="2026-03-02",
        total=Decimal("800.00"),
        subtotal=Decimal("800.00"),
        processing_status=ProcessingState.MANUAL_REVIEW,
        decision=AgentDecision.MANUAL_REVIEW,
    )
    mock_repo.save_record(record)

    payload = {
        "reviewer": "auditor_elena",
        "action": "REJECT",
        "comment": "Fraudulent vendor details detected.",
    }
    rev_resp = client.post("/invoices/INV-BUG-REJECT/review", json=payload, headers=auth_headers)
    assert rev_resp.status_code == 200
    assert rev_resp.json()["final_state"] == "HUMAN_REJECTED"

    # Verify detail
    detail = client.get("/invoices/INV-BUG-REJECT", headers=auth_headers).json()
    assert detail["final_state"] == "HUMAN_REJECTED"
    assert detail["human_review_decision"] == "REJECT"

    # Verify listing filter
    list_manual = client.get("/invoices?status=MANUAL_REVIEW", headers=auth_headers).json()
    assert not any(item["invoice_id"] == "INV-BUG-REJECT" for item in list_manual["items"])

    list_rejected = client.get("/invoices?status=HUMAN_REJECTED", headers=auth_headers).json()
    assert any(item["invoice_id"] == "INV-BUG-REJECT" for item in list_rejected["items"])

    # Verify dashboard
    stats = client.get("/dashboard/stats", headers=auth_headers).json()
    assert stats["human_rejected_count"] >= 1
    assert Decimal(stats["human_rejected_value"]) >= Decimal("800.00")


def test_human_review_cannot_bypass_blocked_safety(client, mock_repo, auth_headers):
    """
    STEP 16 — TEST BLOCK:
    Confirm BLOCKED remains BLOCKED.
    A normal human review action must not bypass Decision Guard.
    """
    record = InvoiceRecord(
        invoice_id="INV-BUG-BLOCKED",
        invoice_number="BUG-003",
        vendor_id="VEND-03",
        vendor_name="Blocked Entity Inc",
        invoice_date="2026-03-03",
        total=Decimal("50000.00"),
        processing_status=ProcessingState.BLOCKED,
        decision=AgentDecision.BLOCK,
    )
    mock_repo.save_record(record)

    # API must forbid review on BLOCKED invoices (409 Conflict)
    payload = {
        "reviewer": "rogue_auditor",
        "action": "APPROVE",
        "comment": "Attempting unauthorized bypass of Decision Guard",
    }
    resp = client.post("/invoices/INV-BUG-BLOCKED/review", json=payload, headers=auth_headers)
    assert resp.status_code == 409
    assert "BLOCKED" in resp.json()["message"]

    # Even if someone directly called derive_final_state with APPROVE, it remains BLOCKED
    assert derive_final_state(automated_decision="BLOCK", human_review_decision="APPROVE", processing_status="BLOCKED") == FinalState.BLOCKED

    # Final state in record remains BLOCKED
    loaded = mock_repo.get_record("INV-BUG-BLOCKED")
    assert loaded.get_final_state() == "BLOCKED"


def test_dashboard_example_scenario_step9(client, mock_repo, auth_headers):
    """
    STEP 9 — DASHBOARD EXAMPLE:
    Suppose:
    Invoice A: AUTO_APPROVE
    Invoice B: MANUAL_REVIEW, not reviewed
    Invoice C: MANUAL_REVIEW -> human APPROVE
    Invoice D: MANUAL_REVIEW -> human REJECT
    Invoice E: BLOCK

    Dashboard should show:
    Auto-approved: 1
    Manual review: 1
    Human approved: 1
    Human rejected: 1
    Blocked: 1

    The invoice for Invoice C must NOT remain counted as active Manual Review.
    """
    mock_repo.records.clear()

    # Invoice A: AUTO_APPROVE
    mock_repo.save_record(InvoiceRecord(
        invoice_id="INV-A",
        invoice_number="A-01",
        vendor_id="V-A",
        vendor_name="Vendor A",
        invoice_date="2026-03-01",
        total=Decimal("100.00"),
        processing_status=ProcessingState.AUTO_APPROVED,
        decision=AgentDecision.AUTO_APPROVE,
    ))

    # Invoice B: MANUAL_REVIEW, not reviewed
    mock_repo.save_record(InvoiceRecord(
        invoice_id="INV-B",
        invoice_number="B-01",
        vendor_id="V-B",
        vendor_name="Vendor B",
        invoice_date="2026-03-01",
        total=Decimal("200.00"),
        processing_status=ProcessingState.MANUAL_REVIEW,
        decision=AgentDecision.MANUAL_REVIEW,
    ))

    # Invoice C: MANUAL_REVIEW -> human APPROVE
    mock_repo.save_record(InvoiceRecord(
        invoice_id="INV-C",
        invoice_number="C-01",
        vendor_id="V-C",
        vendor_name="Vendor C",
        invoice_date="2026-03-01",
        total=Decimal("300.00"),
        processing_status=ProcessingState.MANUAL_REVIEW,
        decision=AgentDecision.MANUAL_REVIEW,
    ))
    client.post("/invoices/INV-C/review", json={"reviewer": "jane", "action": "APPROVE", "comment": "Approved C"}, headers=auth_headers)

    # Invoice D: MANUAL_REVIEW -> human REJECT
    mock_repo.save_record(InvoiceRecord(
        invoice_id="INV-D",
        invoice_number="D-01",
        vendor_id="V-D",
        vendor_name="Vendor D",
        invoice_date="2026-03-01",
        total=Decimal("400.00"),
        processing_status=ProcessingState.MANUAL_REVIEW,
        decision=AgentDecision.MANUAL_REVIEW,
    ))
    client.post("/invoices/INV-D/review", json={"reviewer": "jane", "action": "REJECT", "comment": "Rejected D"}, headers=auth_headers)

    # Invoice E: BLOCK
    mock_repo.save_record(InvoiceRecord(
        invoice_id="INV-E",
        invoice_number="E-01",
        vendor_id="V-E",
        vendor_name="Vendor E",
        invoice_date="2026-03-01",
        total=Decimal("500.00"),
        processing_status=ProcessingState.BLOCKED,
        decision=AgentDecision.BLOCK,
    ))

    stats = client.get("/dashboard/stats", headers=auth_headers).json()
    assert stats["auto_approved_count"] == 1
    assert stats["manual_review_count"] == 1
    assert stats["human_approved_count"] == 1
    assert stats["human_rejected_count"] == 1
    assert stats["blocked_count"] == 1

    # Check decimal values
    assert Decimal(stats["auto_approved_value"]) == Decimal("100.00")
    assert Decimal(stats["manual_review_value"]) == Decimal("200.00")
    assert Decimal(stats["human_approved_value"]) == Decimal("300.00")
    assert Decimal(stats["human_rejected_value"]) == Decimal("400.00")
    assert Decimal(stats["blocked_value"]) == Decimal("500.00")
