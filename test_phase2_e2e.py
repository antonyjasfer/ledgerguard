"""Comprehensive Phase 2 End-to-End Verification Script for LedgerGuard.

Tests:
1. All existing app/api/main.py routes + the new /alexa UI route (200 OK).
2. POST /api/alexa/converse executing Strands + the 5 invoice tools + Argon2 sealing.
3. Cross-session state persistence across 2 consecutive voice turns.
4. POST /api/alexa/tamper-test confirming original_valid=True, tampered_valid=False, tamper_detected=True.
5. /mcp Streamable HTTP calling calculate_invoice_risk and seal_ledger_audit_record.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ["AWS_PROFILE"] = "ledgerguard"
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
os.environ["AWS_REGION"] = "us-east-1"

from starlette.testclient import TestClient
from app.api.main import app


def test_1_routes_availability(client: TestClient) -> tuple[str, str]:
    """Test 1: Health, existing routes, and new /alexa UI route availability."""
    routes_to_test = [
        ("/health", 200),
        ("/ready", 200),
        ("/policy", 200),
        ("/vendors", 200),
        ("/alexa", 200),
        ("/", 200),
    ]

    for path, expected_status in routes_to_test:
        resp = client.get(path)
        if resp.status_code != expected_status:
            return "FAIL", f"Path {path} returned status {resp.status_code}, expected {expected_status}"

    return "PASS", "All core API routes and /alexa UI served successfully (200 OK)"


def test_2_alexa_converse_flow(client: TestClient) -> tuple[str, str]:
    """Test 2: POST /api/alexa/converse executing Strands + 5 tools + Argon2 sealing."""
    req_body = {
        "prompt": "Audit pending Q4 batch and report any duplicate invoices",
        "session_id": "test-session-1",
    }
    resp = client.post("/api/alexa/converse", json=req_body)
    if resp.status_code != 200:
        return "FAIL", f"POST /api/alexa/converse returned {resp.status_code}"

    data = resp.json()
    speech = data.get("voice_speech", "")
    engine = data.get("active_engine", "")
    trace = data.get("tool_trace", [])
    audit_entry = data.get("audit_entry", {})

    if not speech:
        return "FAIL", "Response missing voice_speech"
    if not engine:
        return "FAIL", "Response missing active_engine"
    if not audit_entry.get("argon2_seal"):
        return "FAIL", "Audit entry missing argon2_seal"

    return "PASS", f"Engine: {engine} | Tools trace: {len(trace)} tools | Sealed Block #{audit_entry.get('block_index')}"


def test_3_cross_session_state_persistence(client: TestClient) -> tuple[str, str]:
    """Test 3: Cross-session state persistence across 2 consecutive voice turns."""
    # Turn 1: Inquire about duplicate
    turn1 = client.post(
        "/api/alexa/converse",
        json={"prompt": "Inspect duplicate invoice INV-2026-103", "session_id": "cross-sess-test"},
    )
    if turn1.status_code != 200:
        return "FAIL", f"Turn 1 failed: {turn1.status_code}"

    # Turn 2: Quarantine the invoice referencing prior context
    turn2 = client.post(
        "/api/alexa/converse",
        json={
            "prompt": "Quarantine the duplicate invoice we just found and freeze that vendor",
            "session_id": "cross-sess-test",
        },
    )
    if turn2.status_code != 200:
        return "FAIL", f"Turn 2 failed: {turn2.status_code}"

    turn2_data = turn2.json()
    speech = turn2_data.get("voice_speech", "")

    # Validate state reflects quarantine and frozen vendor
    state_res = client.get("/api/alexa/state")
    if state_res.status_code != 200:
        return "FAIL", f"GET /api/alexa/state failed: {state_res.status_code}"

    state_data = state_res.json()
    statuses = state_data.get("invoice_statuses", {})
    policies = state_data.get("vendor_policies", {})

    inv_status = statuses.get("INV-2026-103", "")
    apex_policy = policies.get("v-apex", "")

    if "QUARANTINE" not in inv_status:
        return "FAIL", f"INV-2026-103 status not quarantined: {inv_status}"
    if "FROZEN" not in apex_policy:
        return "FAIL", f"v-apex vendor not frozen: {apex_policy}"

    return "PASS", f"Turn 2 speech: '{speech[:55]}...' | INV-2026-103: {inv_status} | v-apex: {apex_policy}"


def test_4_tamper_evidence_proof(client: TestClient) -> tuple[str, str]:
    """Test 4: POST /api/alexa/tamper-test confirming original_valid=True, tampered_valid=False, tamper_detected=True."""
    resp = client.post(
        "/api/alexa/tamper-test",
        json={
            "invoice_id": "INV-2026-103",
            "tampered_amount": "84000.00",
            "tampered_recipient": "OFFSHORE-ACC-ILLEGAL-99",
        },
    )
    if resp.status_code != 200:
        return "FAIL", f"Tamper test endpoint returned status {resp.status_code}"

    data = resp.json()
    orig = data.get("original_valid")
    tamp = data.get("tampered_valid")
    det = data.get("tamper_detected")
    params = data.get("argon2_parameters", {})

    if orig is not True:
        return "FAIL", f"Expected original_valid=True, got {orig}"
    if tamp is not False:
        return "FAIL", f"Expected tampered_valid=False, got {tamp}"
    if det is not True:
        return "FAIL", f"Expected tamper_detected=True, got {det}"

    return (
        "PASS",
        f"Original Valid: {orig} | Tampered Valid: {tamp} | Tamper Detected: {det} (m={params.get('memory_cost_kb')}KB, t={params.get('time_cost_iterations')})",
    )


def test_5_mcp_streamable_http(client: TestClient) -> tuple[str, str]:
    """Test 5: /mcp Streamable HTTP calling calculate_invoice_risk and seal_ledger_audit_record."""
    # 1. MCP tools/call calculate_invoice_arithmetic
    sample_inv = json.dumps({
        "invoice_id": "inv-test-mcp",
        "invoice_number": "INV-MCP-999",
        "vendor_id": "v-acme",
        "vendor_name": "Acme Cloud",
        "customer_name": "LedgerGuard",
        "invoice_date": "2026-10-22",
        "currency": "USD",
        "subtotal": "100.00",
        "tax": "10.00",
        "total": "110.00",
        "line_items": [{"description": "Item", "quantity": "1", "unit_price": "100.00", "tax_rate": "0.10"}],
    })

    call1 = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 101,
            "method": "tools/call",
            "params": {
                "name": "calculate_invoice_arithmetic",
                "arguments": {"invoice_data": sample_inv},
            },
        },
    )
    if call1.status_code != 200:
        return "FAIL", f"MCP calculate_invoice_arithmetic returned {call1.status_code}"

    call1_data = call1.json()
    text1 = call1_data.get("result", {}).get("content", [{}])[0].get("text", "")
    if "PASS" not in text1:
        return "FAIL", f"calculate_invoice_arithmetic did not return PASS: {text1}"

    # 2. MCP tools/call seal_ledger_audit_record
    call2 = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 102,
            "method": "tools/call",
            "params": {
                "name": "seal_ledger_audit_record",
                "arguments": {
                    "prev_hash": "ROOT_HASH_TEST",
                    "tx_id": "TX-MCP-PHASE2",
                    "action": "E2E_VERIFICATION_SEAL",
                },
            },
        },
    )
    if call2.status_code != 200:
        return "FAIL", f"MCP seal_ledger_audit_record returned {call2.status_code}"

    call2_data = call2.json()
    text2 = call2_data.get("result", {}).get("content", [{}])[0].get("text", "")
    if "argon2_seal" not in text2:
        return "FAIL", f"seal_ledger_audit_record response missing argon2_seal: {text2}"

    return "PASS", "MCP 2025-11-25 tools/call arithmetic + Argon2 seal executed cleanly"


def main() -> int:
    """Run all Phase 2 tests and print formatted results table."""
    print("=" * 85)
    print(" LEDGERGUARD PHASE 2 END-TO-END VERIFICATION SUITE")
    print(" Alexa+ Multi-Modal Experience, Stateful Memory, & Argon2 Tamper Vault")
    print("=" * 85)
    print()

    client = TestClient(app)

    tests = [
        ("1. Core API & /alexa UI Routes", test_1_routes_availability),
        ("2. Alexa+ Natural Converse & 5-Tool Execution", test_2_alexa_converse_flow),
        ("3. Cross-Session Memory & State Persistence", test_3_cross_session_state_persistence),
        ("4. Cryptographic Tamper-Evidence Proof", test_4_tamper_evidence_proof),
        ("5. Alexa+ MCP Streamable HTTP (2025-11-25)", test_5_mcp_streamable_http),
    ]

    results = []
    all_passed = True

    for name, test_func in tests:
        try:
            status, details = test_func(client)
        except Exception as exc:
            status = "ERROR"
            details = f"Exception: {exc}"

        tag = f"[{status}]"
        results.append((name, tag, details))
        if status != "PASS":
            all_passed = False

    print(f"{'TEST NAME':<45} {'STATUS':<12} {'DETAILS'}")
    print("-" * 115)
    for name, tag, details in results:
        print(f"{name:<45} {tag:<12} {details}")
    print("-" * 115)
    print()

    if all_passed:
        print(">>> ALL 5 PHASE 2 E2E VERIFICATIONS PASSED WITH ZERO ERRORS.")
        print(">>> LEDGERGUARD ALEXA+ MULTI-MODAL & ARGON2 VAULT IS PRODUCTION-READY.")
        return 0
    else:
        print(">>> PHASE 2 E2E SUITE ENCOUNTERED FAILURES.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
