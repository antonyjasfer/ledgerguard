"""Unit tests for the Strands @tool wrappers in app/agent/tools.py.

These tests call the wrapper functions directly (as plain Python functions)
to verify the dict->Pydantic->deterministic->JSON pipeline works correctly.
No LLM, no Bedrock, no AWS calls.
"""

import json
from decimal import Decimal

import pytest

from app.agent.agent import create_ledgerguard_agent
from app.agent.tools import (
    calculate_invoice_arithmetic,
    check_duplicate_invoice,
    get_vendor_history,
    evaluate_invoice_policy,
    calculate_invoice_risk,
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


class TestCalculateInvoiceArithmetic:
    def test_pass_case(self):
        inv = _make_invoice_dict()
        result = json.loads(calculate_invoice_arithmetic(json.dumps(inv)))
        assert result["passed"] is True
        assert result["status"] == "PASS"

    def test_fail_case(self):
        inv = _make_invoice_dict(total="9999.99")
        result = json.loads(calculate_invoice_arithmetic(json.dumps(inv)))
        assert result["passed"] is False
        assert result["status"] == "FAIL"

    def test_alias_compatibility(self):
        inv = _make_invoice_dict()
        result = json.loads(verify_invoice_arithmetic(json.dumps(inv)))
        assert result["passed"] is True


class TestCheckDuplicateInvoice:
    def test_no_duplicate(self):
        """Different vendor = no duplicate."""
        candidate = _make_invoice_dict(invoice_id="NEW1", invoice_number="INV-NEW", vendor_id="V999")
        history = [_make_invoice_dict()]
        result = json.loads(check_duplicate_invoice(json.dumps(candidate), json.dumps(history)))
        assert result["status"] == "NO_DUPLICATE"

    def test_confirmed_duplicate(self):
        """Same vendor + same invoice number, but different invoice_id = CONFIRMED_DUPLICATE."""
        candidate = _make_invoice_dict(invoice_id="NEW2")
        history = [_make_invoice_dict(invoice_id="OLD1")]
        result = json.loads(check_duplicate_invoice(json.dumps(candidate), json.dumps(history)))
        assert result["status"] == "CONFIRMED_DUPLICATE"

    def test_alias_compatibility(self):
        candidate = _make_invoice_dict(invoice_id="NEW1", invoice_number="INV-NEW", vendor_id="V999")
        result = json.loads(check_invoice_duplicates(json.dumps(candidate), json.dumps([])))
        assert result["status"] == "NO_DUPLICATE"


class TestGetVendorHistory:
    def test_established_vendor(self):
        history = [_make_invoice_dict(invoice_id=f"INV{i}") for i in range(5)]
        result = json.loads(get_vendor_history("V100", json.dumps(history)))
        assert result["vendor_id"] == "V100"
        assert result["invoice_count"] == 5
        assert result["new_vendor"] is False

    def test_new_vendor(self):
        result = json.loads(get_vendor_history("V999", json.dumps([])))
        assert result["vendor_id"] == "V999"
        assert result["invoice_count"] == 0
        assert result["new_vendor"] is True

    def test_alias_compatibility(self):
        result = json.loads(get_vendor_history_tool("V999", json.dumps([])))
        assert result["vendor_id"] == "V999"


class TestEvaluateInvoicePolicy:
    def test_clean_policy(self):
        """Small-amount invoice, established vendor, no duplicates -> policy pass."""
        inv = _make_invoice_dict(subtotal="100.00", tax="5.00", discount="0.00", total="105.00",
                                  line_items=[{"description": "Item", "quantity": "1", "unit_price": "100.00"}])
        vendor_result = get_vendor_history("V100", json.dumps(
            [_make_invoice_dict(invoice_id=f"HIST{i}") for i in range(5)]
        ))
        dup_result = check_duplicate_invoice(json.dumps(inv), json.dumps([]))
        result = json.loads(evaluate_invoice_policy(json.dumps(inv), vendor_result, dup_result))
        assert result["passed"] is True
        assert result["should_block"] is False

    def test_alias_compatibility(self):
        inv = _make_invoice_dict(subtotal="100.00", tax="5.00", discount="0.00", total="105.00",
                                  line_items=[{"description": "Item", "quantity": "1", "unit_price": "100.00"}])
        vendor_result = get_vendor_history("V100", json.dumps([]))
        dup_result = check_duplicate_invoice(json.dumps(inv), json.dumps([]))
        result = json.loads(evaluate_invoice_policy_tool(json.dumps(inv), vendor_result, dup_result))
        assert "passed" in result


class TestCalculateInvoiceRisk:
    def test_low_risk(self):
        """Small-amount, established vendor, no duplicates -> LOW risk."""
        inv = _make_invoice_dict(subtotal="100.00", tax="5.00", discount="0.00", total="105.00",
                                  line_items=[{"description": "Item", "quantity": "1", "unit_price": "100.00"}])
        inv_json = json.dumps(inv)
        arith_result = calculate_invoice_arithmetic(inv_json)
        dup_result = check_duplicate_invoice(inv_json, json.dumps([]))
        vendor_result = get_vendor_history("V100", json.dumps(
            [_make_invoice_dict(invoice_id=f"HIST{i}") for i in range(5)]
        ))
        policy_result = evaluate_invoice_policy(inv_json, vendor_result, dup_result)
        result = json.loads(calculate_invoice_risk(arith_result, dup_result, vendor_result, policy_result, inv_json))
        assert result["risk_level"] == "LOW"
        assert result["recommended_action"] == "AUTO_APPROVE"

    def test_alias_compatibility(self):
        inv = _make_invoice_dict(subtotal="100.00", tax="5.00", discount="0.00", total="105.00",
                                  line_items=[{"description": "Item", "quantity": "1", "unit_price": "100.00"}])
        inv_json = json.dumps(inv)
        arith_result = verify_invoice_arithmetic(inv_json)
        dup_result = check_invoice_duplicates(inv_json, json.dumps([]))
        vendor_result = get_vendor_history_tool("V100", json.dumps([]))
        policy_result = evaluate_invoice_policy_tool(inv_json, vendor_result, dup_result)
        result = json.loads(calculate_invoice_risk_tool(arith_result, dup_result, vendor_result, policy_result, inv_json))
        assert "risk_level" in result


class TestLedgerguardToolsList:
    def test_five_tools_registered(self):
        assert len(LEDGERGUARD_TOOLS) == 5

    def test_tool_names_match_spec(self):
        expected_names = [
            "calculate_invoice_arithmetic",
            "check_duplicate_invoice",
            "get_vendor_history",
            "evaluate_invoice_policy",
            "calculate_invoice_risk",
        ]
        tool_names = [t.tool_name for t in LEDGERGUARD_TOOLS]
        assert tool_names == expected_names

    def test_tools_are_callable(self):
        for t in LEDGERGUARD_TOOLS:
            assert callable(t)

    def test_agent_registers_tools_on_creation(self):
        """Verifies create_ledgerguard_agent registers all 5 tools with expected names."""
        from unittest.mock import MagicMock
        mock_model = MagicMock()
        agent = create_ledgerguard_agent(model=mock_model, include_tools=True)
        expected_names = [
            "calculate_invoice_arithmetic",
            "check_duplicate_invoice",
            "get_vendor_history",
            "evaluate_invoice_policy",
            "calculate_invoice_risk",
        ]
        assert agent.tool_names == expected_names
