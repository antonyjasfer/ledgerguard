"""Unit tests for the Strands @tool wrappers in app/agent/tools.py.

These tests call the wrapper functions directly (as plain Python functions)
to verify the dict->Pydantic->deterministic->JSON pipeline works correctly.
No LLM, no Bedrock, no AWS calls.
"""

import json
from decimal import Decimal

import pytest

from app.agent.tools import (
    verify_invoice_arithmetic,
    check_invoice_duplicates,
    get_vendor_history_tool,
    evaluate_invoice_policy_tool,
    calculate_invoice_risk_tool,
    LEDGERGUARD_TOOLS,
)


def _make_invoice_dict(
    invoice_id="INV001",
    invoice_number="INV-2025-001",
    vendor_id="V100",
    vendor_name="Acme Corp",
    customer_name="LedgerGuard LLC",
    invoice_date="2025-06-01",
    currency="USD",
    subtotal="1000.00",
    tax="50.00",
    discount="0.00",
    total="1050.00",
    line_items=None,
):
    if line_items is None:
        line_items = [
            {"description": "Widget A", "quantity": "10", "unit_price": "100.00"},
        ]
    return {
        "invoice_id": invoice_id,
        "invoice_number": invoice_number,
        "vendor_id": vendor_id,
        "vendor_name": vendor_name,
        "customer_name": customer_name,
        "invoice_date": invoice_date,
        "currency": currency,
        "subtotal": subtotal,
        "tax": tax,
        "discount": discount,
        "total": total,
        "line_items": line_items,
    }


class TestVerifyInvoiceArithmetic:
    def test_pass_case(self):
        inv = _make_invoice_dict()
        result = json.loads(verify_invoice_arithmetic(json.dumps(inv)))
        assert result["passed"] is True
        assert result["status"] == "PASS"

    def test_fail_case(self):
        inv = _make_invoice_dict(total="9999.99")
        result = json.loads(verify_invoice_arithmetic(json.dumps(inv)))
        assert result["passed"] is False
        assert result["status"] == "FAIL"


class TestCheckInvoiceDuplicates:
    def test_no_duplicate(self):
        """Different vendor = no duplicate."""
        candidate = _make_invoice_dict(invoice_id="NEW1", invoice_number="INV-NEW", vendor_id="V999")
        history = [_make_invoice_dict()]
        result = json.loads(check_invoice_duplicates(json.dumps(candidate), json.dumps(history)))
        assert result["status"] == "NO_DUPLICATE"

    def test_confirmed_duplicate(self):
        """Same vendor + same invoice number, but different invoice_id = CONFIRMED_DUPLICATE."""
        candidate = _make_invoice_dict(invoice_id="NEW2")
        history = [_make_invoice_dict(invoice_id="OLD1")]
        result = json.loads(check_invoice_duplicates(json.dumps(candidate), json.dumps(history)))
        assert result["status"] == "CONFIRMED_DUPLICATE"


class TestGetVendorHistory:
    def test_established_vendor(self):
        history = [_make_invoice_dict(invoice_id=f"INV{i}") for i in range(5)]
        result = json.loads(get_vendor_history_tool("V100", json.dumps(history)))
        assert result["vendor_id"] == "V100"
        assert result["invoice_count"] == 5
        assert result["new_vendor"] is False

    def test_new_vendor(self):
        result = json.loads(get_vendor_history_tool("V999", json.dumps([])))
        assert result["vendor_id"] == "V999"
        assert result["invoice_count"] == 0
        assert result["new_vendor"] is True


class TestEvaluateInvoicePolicy:
    def test_clean_policy(self):
        """Small-amount invoice, established vendor, no duplicates -> policy pass."""
        inv = _make_invoice_dict(subtotal="100.00", tax="5.00", discount="0.00", total="105.00",
                                  line_items=[{"description": "Item", "quantity": "1", "unit_price": "100.00"}])
        vendor_result = get_vendor_history_tool("V100", json.dumps(
            [_make_invoice_dict(invoice_id=f"HIST{i}") for i in range(5)]
        ))
        dup_result = check_invoice_duplicates(json.dumps(inv), json.dumps([]))
        result = json.loads(evaluate_invoice_policy_tool(json.dumps(inv), vendor_result, dup_result))
        assert result["passed"] is True
        assert result["should_block"] is False


class TestCalculateInvoiceRisk:
    def test_low_risk(self):
        """Small-amount, established vendor, no duplicates -> LOW risk."""
        inv = _make_invoice_dict(subtotal="100.00", tax="5.00", discount="0.00", total="105.00",
                                  line_items=[{"description": "Item", "quantity": "1", "unit_price": "100.00"}])
        inv_json = json.dumps(inv)
        arith_result = verify_invoice_arithmetic(inv_json)
        dup_result = check_invoice_duplicates(inv_json, json.dumps([]))
        vendor_result = get_vendor_history_tool("V100", json.dumps(
            [_make_invoice_dict(invoice_id=f"HIST{i}") for i in range(5)]
        ))
        policy_result = evaluate_invoice_policy_tool(inv_json, vendor_result, dup_result)
        result = json.loads(calculate_invoice_risk_tool(arith_result, dup_result, vendor_result, policy_result, inv_json))
        assert result["risk_level"] == "LOW"
        assert result["recommended_action"] == "AUTO_APPROVE"


class TestLedgerguardToolsList:
    def test_five_tools_registered(self):
        assert len(LEDGERGUARD_TOOLS) == 5

    def test_tools_are_callable(self):
        for t in LEDGERGUARD_TOOLS:
            assert callable(t)
