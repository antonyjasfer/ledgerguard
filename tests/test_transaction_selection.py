"""Tests for Phase 2: Transaction selection correctness and zero guessing.

Verifies:
1. Mentioning TX-901, TX-902, or unknown ID never substitutes another invoice.
2. Unrecognized transaction IDs cause zero mutation.
3. Actions without transaction specification ask for specification rather than guessing.
4. Consequential actions accurately mutate the intended invoice.
"""

import pytest
from fastapi.testclient import TestClient

from app.api.main import app
from app.api.routes.alexa_plus import get_alexa_service


@pytest.fixture
def client():
    return TestClient(app)


def test_unknown_transaction_id_not_substituted(client):
    """User specifying TX-901 or TX-902 must NOT select or mutate another invoice."""
    service = get_alexa_service()
    init_status_103 = service.invoice_statuses.get("INV-2026-103")

    resp = client.post(
        "/api/alexa/converse",
        json={"prompt": "Quarantine invoice TX-902 immediately and freeze the vendor"}
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["intent"] == "TRANSACTION_NOT_FOUND"
    assert "TX-902" in data["voice_speech"]
    assert "not found" in data["voice_speech"].lower()
    assert "no changes were made" in data["voice_speech"].lower()

    # Ensure INV-2026-103 was NOT mutated
    assert service.invoice_statuses.get("INV-2026-103") == init_status_103


def test_action_without_selection_requires_specification(client):
    """Calling quarantine without selecting or naming an invoice asks for specification."""
    service = get_alexa_service()
    service.last_referenced_invoice_id = None  # Clear previous reference

    resp = client.post(
        "/api/alexa/converse",
        json={"prompt": "Please quarantine this invoice"}
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["intent"] == "SPECIFICATION_REQUIRED"
    assert "specify" in data["voice_speech"].lower()


def test_explicit_valid_transaction_actions_correctly(client):
    """Explicitly selecting INV-2026-102 actions that exact invoice."""
    resp = client.post(
        "/api/alexa/action",
        json={"invoice_id": "INV-2026-102", "action": "QUARANTINE_AND_DISPUTE", "notes": "Arithmetic mismatch"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["invoice_id"] == "INV-2026-102"
    assert data["new_status"] == "QUARANTINED_DISPUTED"

    service = get_alexa_service()
    assert service.invoice_statuses["INV-2026-102"] == "QUARANTINED_DISPUTED"


def test_action_on_nonexistent_invoice_returns_404(client):
    """Direct action endpoint rejects non-existent transaction with 404."""
    resp = client.post(
        "/api/alexa/action",
        json={"invoice_id": "TX-UNKNOWN-999", "action": "APPROVE_AND_SEAL"}
    )
    assert resp.status_code == 404
    assert "not found" in (resp.json().get("message") or resp.json().get("detail", "")).lower()


def test_action_with_unsupported_operation_returns_400(client):
    """Unsupported action is rejected with 400 Bad Request."""
    resp = client.post(
        "/api/alexa/action",
        json={"invoice_id": "INV-2026-101", "action": "UNSUPPORTED_ACTION"}
    )
    assert resp.status_code == 400

