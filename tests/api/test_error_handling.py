"""Offline unit tests verifying structured, non-leaking error responses."""

from unittest.mock import MagicMock
from fastapi import APIRouter
from app.api.dependencies import require_api_key
from app.api.errors import InvalidInvoiceError


def test_structured_error_schema_404(client, auth_headers):
    """404 error adheres strictly to ErrorResponse schema."""
    response = client.get("/invoices/nonexistent_id", headers=auth_headers)
    assert response.status_code == 404
    data = response.json()
    assert "error" in data
    assert "message" in data
    assert "request_id" in data
    assert data["error"] == "INVOICE_NOT_FOUND"


def test_validation_error_schema_422(client, auth_headers):
    """Schema validation error formats field details safely."""
    response = client.post("/invoices", json={"invalid": "payload"}, headers=auth_headers)
    assert response.status_code == 422
    data = response.json()
    assert data["error"] == "VALIDATION_ERROR"
    assert "validation_errors" in data["details"]


def test_unhandled_exception_does_not_leak_stack_trace(app, auth_headers):
    """500 internal server errors mask stack traces and internal exceptions."""
    from fastapi.testclient import TestClient
    client = TestClient(app, raise_server_exceptions=False)

    test_router = APIRouter()

    @test_router.get("/test-crash")
    def trigger_crash():
        raise RuntimeError("Internal DB connection string: aws://secret_pass@10.0.0.1")

    app.include_router(test_router)

    response = client.get("/test-crash", headers=auth_headers)
    assert response.status_code == 500
    data = response.json()
    assert data["error"] == "INTERNAL_SERVER_ERROR"
    assert "secret_pass" not in str(data)
    assert "RuntimeError" not in str(data)
    assert "Traceback" not in str(data)
