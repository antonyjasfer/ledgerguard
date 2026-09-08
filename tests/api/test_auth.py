"""Offline unit tests for API authentication boundary."""


def test_protected_route_missing_api_key(client):
    """Accessing protected endpoint without API key returns 401 Unauthorized."""
    response = client.get("/invoices/inv_123")
    assert response.status_code == 401
    data = response.json()
    assert data["error"] == "UNAUTHORIZED"
    assert "Missing API key" in data["message"]


def test_protected_route_invalid_api_key(client):
    """Accessing protected endpoint with incorrect API key returns 401 Unauthorized."""
    response = client.get("/invoices/inv_123", headers={"X-API-Key": "wrong-key"})
    assert response.status_code == 401
    data = response.json()
    assert data["error"] == "UNAUTHORIZED"
    assert "Invalid API key" in data["message"]


def test_protected_route_valid_api_key_header(client, mock_repo, auth_headers):
    """Accessing protected endpoint with valid X-API-Key header succeeds."""
    response = client.get("/invoices/nonexistent", headers=auth_headers)
    # Auth passed, invoice not found is expected
    assert response.status_code == 404
    assert response.json()["error"] == "INVOICE_NOT_FOUND"


def test_protected_route_valid_bearer_token(client, mock_repo):
    """Accessing protected endpoint with valid Authorization: Bearer succeeds."""
    response = client.get("/invoices/nonexistent", headers={"Authorization": "Bearer test-secret-key"})
    assert response.status_code == 404
    assert response.json()["error"] == "INVOICE_NOT_FOUND"


def test_health_does_not_require_auth(client):
    """Health endpoints remain publicly accessible without API keys."""
    response = client.get("/health")
    assert response.status_code == 200
