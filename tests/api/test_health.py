"""Offline unit tests for health and readiness endpoints."""


def test_health_liveness_probe(client):
    """Verify /health returns 200 OK without requiring authentication."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "ledgerguard"
    assert data["version"] == "0.1.0"
    assert "X-Request-ID" in response.headers


def test_ready_probe(client):
    """Verify /ready validates configuration settings safely."""
    response = client.get("/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["dependencies"]["dynamodb_table_configured"] is True
    assert data["dependencies"]["s3_bucket_configured"] is True
    assert data["dependencies"]["sqs_queue_configured"] is True


def test_request_correlation_id_propagated(client):
    """Client-supplied X-Request-ID header is echoed in the response header."""
    custom_id = "test-req-custom-999"
    response = client.get("/health", headers={"X-Request-ID": custom_id})
    assert response.status_code == 200
    assert response.headers.get("X-Request-ID") == custom_id
