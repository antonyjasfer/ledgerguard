"""Tests for Phase 5: Cryptographic audit chain verification and tamper detection."""

import copy
import pytest
from fastapi.testclient import TestClient

from app.api.main import app
from app.api.routes.alexa_plus import get_alexa_service
from connectors.argon_connector import get_argon_connector


@pytest.fixture
def client():
    return TestClient(app)


def test_valid_chain_verifies_successfully():
    """An untouched audit chain from genesis must verify as 100% valid."""
    service = get_alexa_service()
    chain = service.audit_chain
    assert len(chain) >= 2

    vault = get_argon_connector()
    result = vault.verify_chain_integrity(chain)
    assert result["is_valid"] is True
    assert result["tampered_blocks"] == []
    assert result["verification_status"] == "TAMPER_FREE_VERIFIED"
    assert result["total_blocks"] == len(chain)


def test_tampered_payload_detected():
    """Modifying action or tx_id in a block must cause verification failure."""
    service = get_alexa_service()
    tampered_chain = copy.deepcopy(service.audit_chain)

    # Tamper with block index 1
    tampered_chain[1]["action"] = "UNAUTHORIZED_FORGED_ACTION"

    vault = get_argon_connector()
    result = vault.verify_chain_integrity(tampered_chain)
    assert result["is_valid"] is False
    assert 1 in result["tampered_blocks"]
    assert result["verification_status"] == "TAMPERING_DETECTED"


def test_broken_previous_hash_link_detected():
    """Altering prev_hash in an intermediate block must break link and fail verification."""
    service = get_alexa_service()
    tampered_chain = copy.deepcopy(service.audit_chain)

    # Break hash link at block 1
    tampered_chain[1]["prev_hash"] = "FORGED_PREVIOUS_HASH_" + ("0" * 40)

    vault = get_argon_connector()
    result = vault.verify_chain_integrity(tampered_chain)
    assert result["is_valid"] is False
    assert 1 in result["tampered_blocks"]


def test_deleted_block_breaks_continuity():
    """Deleting a block must break SHA-256 linkage and index continuity."""
    service = get_alexa_service()
    tampered_chain = copy.deepcopy(service.audit_chain)
    if len(tampered_chain) > 2:
        del tampered_chain[1]  # Delete block 1

        vault = get_argon_connector()
        result = vault.verify_chain_integrity(tampered_chain)
        assert result["is_valid"] is False
        assert len(result["tampered_blocks"]) > 0


def test_audit_verify_api_endpoint(client):
    """POST /api/alexa/audit/verify returns complete verification status."""
    resp = client.post("/api/alexa/audit/verify")
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_valid"] is True
    assert data["algorithm"] == "argon2id-sha256-hash-chain"
    assert "total_blocks" in data
