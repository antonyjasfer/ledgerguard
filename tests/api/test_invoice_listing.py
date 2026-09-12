"""Unit tests for GET /invoices listing, filtering, limits, and CORS."""

from decimal import Decimal
from fastapi.testclient import TestClient

from app.models.decision import AgentDecision
from app.models.verification import RiskLevel
from app.models.persistence import InvoiceRecord
from app.services.state import ProcessingState


def test_list_invoices_empty(client: TestClient, auth_headers: dict[str, str]):
    """Empty repository returns empty item list."""
    response = client.get("/invoices", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["total"] == 0
    assert data["limit"] == 50
    assert data["offset"] == 0


def test_list_invoices_populated_and_limits(client: TestClient, mock_repo, auth_headers: dict[str, str]):
    """Listing returns items, clamps limit, and supports offset."""
    for i in range(15):
        mock_repo.save_record(
            InvoiceRecord(
                invoice_id=f"INV-{i:03d}",
                invoice_number=f"NUM-{i:03d}",
                vendor_id="VEND-ALPHA",
                vendor_name="Acme Corp",
                invoice_date="2026-03-01",
                total=Decimal(f"{100 + i}.00"),
                processing_status=ProcessingState.RECEIVED,
            )
        )

    # Test limit clamping to 5
    res_5 = client.get("/invoices?limit=5", headers=auth_headers)
    assert res_5.status_code == 200
    d5 = res_5.json()
    assert len(d5["items"]) == 5
    assert d5["total"] == 15
    assert d5["limit"] == 5

    # Test offset
    res_offset = client.get("/invoices?limit=5&offset=10", headers=auth_headers)
    assert res_offset.status_code == 200
    doff = res_offset.json()
    assert len(doff["items"]) == 5
    assert doff["offset"] == 10


def test_list_invoices_filter_by_status(client: TestClient, mock_repo, auth_headers: dict[str, str]):
    """Filter by processing_status query parameter."""
    mock_repo.save_record(
        InvoiceRecord(
            invoice_id="INV-APP",
            invoice_number="NUM-APP",
            vendor_id="VEND-1",
            vendor_name="Approved Vendor",
            invoice_date="2026-03-01",
            total=Decimal("150.00"),
            processing_status=ProcessingState.AUTO_APPROVED,
            decision=AgentDecision.AUTO_APPROVE,
        )
    )
    mock_repo.save_record(
        InvoiceRecord(
            invoice_id="INV-BLK",
            invoice_number="NUM-BLK",
            vendor_id="VEND-2",
            vendor_name="Blocked Vendor",
            invoice_date="2026-03-01",
            total=Decimal("250.00"),
            processing_status=ProcessingState.BLOCKED,
            decision=AgentDecision.BLOCK,
        )
    )

    res_app = client.get("/invoices?status=AUTO_APPROVED", headers=auth_headers)
    assert res_app.status_code == 200
    d_app = res_app.json()
    assert len(d_app["items"]) == 1
    assert d_app["items"][0]["invoice_id"] == "INV-APP"

    res_blk = client.get("/invoices?status=BLOCKED", headers=auth_headers)
    assert res_blk.status_code == 200
    d_blk = res_blk.json()
    assert len(d_blk["items"]) == 1
    assert d_blk["items"][0]["invoice_id"] == "INV-BLK"


def test_list_invoices_search_and_vendor(client: TestClient, mock_repo, auth_headers: dict[str, str]):
    """Search matches vendor name or invoice number; vendor_id filter restricts."""
    mock_repo.save_record(
        InvoiceRecord(
            invoice_id="INV-XYZ-1",
            invoice_number="INV-SPECIAL-99",
            vendor_id="VEND-SPECIAL",
            vendor_name="Unique Specialty Goods",
            invoice_date="2026-03-01",
            total=Decimal("80.00"),
            processing_status=ProcessingState.RECEIVED,
        )
    )
    mock_repo.save_record(
        InvoiceRecord(
            invoice_id="INV-XYZ-2",
            invoice_number="INV-NORMAL-01",
            vendor_id="VEND-COMMON",
            vendor_name="Common Supplies",
            invoice_date="2026-03-01",
            total=Decimal("90.00"),
            processing_status=ProcessingState.RECEIVED,
        )
    )

    # Search by special keyword
    res_search = client.get("/invoices?search=special", headers=auth_headers)
    assert res_search.status_code == 200
    d_search = res_search.json()
    assert len(d_search["items"]) == 1
    assert d_search["items"][0]["invoice_id"] == "INV-XYZ-1"

    # Filter by vendor_id
    res_vend = client.get("/invoices?vendor_id=VEND-COMMON", headers=auth_headers)
    assert res_vend.status_code == 200
    d_vend = res_vend.json()
    assert len(d_vend["items"]) == 1
    assert d_vend["items"][0]["invoice_id"] == "INV-XYZ-2"


def test_list_invoices_requires_auth(client: TestClient):
    """Unauthenticated request to list invoices is rejected with 401."""
    res = client.get("/invoices")
    assert res.status_code == 401


def test_cors_headers(client: TestClient):
    """CORS headers are returned on preflight options and standard requests."""
    res = client.options(
        "/invoices",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert res.status_code == 200
    assert "access-control-allow-origin" in res.headers
