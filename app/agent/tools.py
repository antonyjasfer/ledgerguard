"""Strands tool wrappers for LedgerGuard deterministic verification functions.

Each wrapper delegates to the corresponding deterministic implementation.
No business logic is duplicated here. The wrappers adapt typed Pydantic models
to/from the dict-based interface that Strands tool calling uses.
"""

import json
from datetime import date
from decimal import Decimal
from typing import Any

from strands import tool

from app.models.invoice import Invoice, LineItem
from app.models.policy import PolicyConfig
from app.tools.anomaly import scan_invoice_anomalies as _anomaly
from app.tools.arithmetic import calculate_invoice_arithmetic as _arithmetic
from app.tools.duplicates import check_duplicate_invoice as _duplicates
from app.tools.policy import evaluate_invoice_policy as _policy
from app.tools.risk import calculate_invoice_risk as _risk
from app.tools.vendor_history import get_vendor_history as _vendor_history


def _dict_to_invoice(data: dict) -> Invoice:
    """Convert a dict (from LLM tool call) into an Invoice model."""
    line_items = []
    for li in data.get("line_items", []):
        line_items.append(LineItem(
            description=li["description"],
            quantity=Decimal(str(li.get("quantity", "1"))),
            unit_price=Decimal(str(li["unit_price"])),
            tax_rate=Decimal(str(li.get("tax_rate", "0.00"))),
            discount=Decimal(str(li.get("discount", "0.00"))),
        ))

    def _dec(v: Any) -> Decimal | None:
        if v is None:
            return None
        return Decimal(str(v))

    return Invoice(
        invoice_id=data["invoice_id"],
        invoice_number=data["invoice_number"],
        vendor_id=data["vendor_id"],
        vendor_name=data["vendor_name"],
        customer_name=data["customer_name"],
        invoice_date=date.fromisoformat(data["invoice_date"]) if isinstance(data["invoice_date"], str) else data["invoice_date"],
        currency=data.get("currency", "USD"),
        subtotal=_dec(data.get("subtotal")),
        tax=_dec(data.get("tax")),
        discount=_dec(data.get("discount")),
        total=_dec(data.get("total")),
        line_items=line_items,
        metadata=data.get("metadata", {}),
    )


@tool(
    name="calculate_invoice_arithmetic",
    description=(
        "Verify whether invoice arithmetic is internally consistent using deterministic "
        "Decimal calculations. Checks line item subtotals (quantity * unit_price), subtotal "
        "summation, tax, discount, and grand total. Use this when invoice monetary fields "
        "and line items are available. Returns PASS, FAIL, or INSUFFICIENT_DATA."
    ),
)
def calculate_invoice_arithmetic(invoice_data: str) -> str:
    """Run deterministic arithmetic verification on a JSON-serialized invoice.

    Args:
        invoice_data: JSON string containing the invoice to verify.

    Returns:
        JSON string with the ArithmeticVerificationResult.
    """
    data = json.loads(invoice_data)
    invoice = _dict_to_invoice(data)
    result = _arithmetic(invoice)
    return result.model_dump_json()


@tool(
    name="check_duplicate_invoice",
    description=(
        "Check whether a candidate invoice is a duplicate of any historical invoice. "
        "Returns CONFIRMED_DUPLICATE (same vendor and invoice number), POSSIBLE_DUPLICATE "
        "(same vendor, amount, and date within 7 days), or NO_DUPLICATE. Use this to detect "
        "duplicate payment risk."
    ),
)
def check_duplicate_invoice(invoice_data: str, historical_invoices: str) -> str:
    """Run deterministic duplicate detection against historical records.

    Args:
        invoice_data: JSON string containing the candidate invoice.
        historical_invoices: JSON string containing a list of historical invoices.

    Returns:
        JSON string with the DuplicateCheckResult.
    """
    inv = _dict_to_invoice(json.loads(invoice_data))
    history = [_dict_to_invoice(h) for h in json.loads(historical_invoices)]
    result = _duplicates(inv, history)
    return result.model_dump_json()


@tool(
    name="get_vendor_history",
    description=(
        "Retrieve aggregated historical metrics for a vendor including invoice count, "
        "total spend by currency, average and maximum amounts, date range, and whether "
        "the vendor is new. Use this to assess vendor reliability and spending patterns."
    ),
)
def get_vendor_history(vendor_id: str, historical_invoices: str) -> str:
    """Compute vendor history from historical invoice records.

    Args:
        vendor_id: The vendor identifier to look up.
        historical_invoices: JSON string containing a list of historical invoices.

    Returns:
        JSON string with the VendorHistoryResult.
    """
    history = [_dict_to_invoice(h) for h in json.loads(historical_invoices)]
    result = _vendor_history(vendor_id, history)
    return json.dumps({
        "vendor_id": result.vendor_id,
        "invoice_count": result.invoice_count,
        "total_spend": {k: str(v) for k, v in result.total_spend.items()},
        "average_invoice_amount": {k: str(v) for k, v in result.average_invoice_amount.items()},
        "largest_invoice_amount": {k: str(v) for k, v in result.largest_invoice_amount.items()},
        "first_invoice_date": str(result.first_invoice_date) if result.first_invoice_date else None,
        "last_invoice_date": str(result.last_invoice_date) if result.last_invoice_date else None,
        "currency_distribution": {k: str(v) for k, v in result.currency_distribution.items()},
        "recent_invoice_count": result.recent_invoice_count,
        "new_vendor": result.new_vendor,
    })


@tool(
    name="evaluate_invoice_policy",
    description=(
        "Evaluate an invoice against corporate Accounts Payable policies including "
        "auto-approval limits, high-value thresholds, new vendor rules, and duplicate "
        "payment blocks. Returns pass/review/block status with specific violations."
    ),
)
def evaluate_invoice_policy(
    invoice_data: str,
    vendor_history_json: str,
    duplicate_result_json: str,
) -> str:
    """Evaluate invoice against AP policies using prior verification results.

    Args:
        invoice_data: JSON string containing the invoice.
        vendor_history_json: JSON result from get_vendor_history tool.
        duplicate_result_json: JSON result from check_invoice_duplicates tool.

    Returns:
        JSON string with the PolicyVerificationResult.
    """
    invoice = _dict_to_invoice(json.loads(invoice_data))
    from app.models.verification import DuplicateCheckResult, VendorHistoryResult
    vendor = VendorHistoryResult.model_validate_json(vendor_history_json)
    dup = DuplicateCheckResult.model_validate_json(duplicate_result_json)
    result = _policy(invoice, vendor, dup)
    return result.model_dump_json()


@tool(
    name="calculate_invoice_risk",
    description=(
        "Calculate a composite risk score (0-100) for an invoice based on arithmetic, "
        "duplicate, vendor, and policy verification results. Returns risk level (LOW, "
        "MEDIUM, HIGH, CRITICAL) and recommended action (AUTO_APPROVE, MANUAL_REVIEW, BLOCK). "
        "Confirmed duplicates always produce CRITICAL risk."
    ),
)
def calculate_invoice_risk(
    arithmetic_result_json: str,
    duplicate_result_json: str,
    vendor_history_json: str,
    policy_result_json: str,
    invoice_data: str,
) -> str:
    """Compute deterministic risk score from all prior verification outputs.

    Args:
        arithmetic_result_json: JSON result from verify_invoice_arithmetic tool.
        duplicate_result_json: JSON result from check_invoice_duplicates tool.
        vendor_history_json: JSON result from get_vendor_history tool.
        policy_result_json: JSON result from evaluate_invoice_policy tool.
        invoice_data: JSON string containing the invoice.

    Returns:
        JSON string with the RiskResult.
    """
    from app.models.verification import (
        ArithmeticVerificationResult,
        DuplicateCheckResult,
        PolicyVerificationResult,
        VendorHistoryResult,
    )

    arithmetic = ArithmeticVerificationResult.model_validate_json(arithmetic_result_json)
    duplicate = DuplicateCheckResult.model_validate_json(duplicate_result_json)
    vendor = VendorHistoryResult.model_validate_json(vendor_history_json)
    policy = PolicyVerificationResult.model_validate_json(policy_result_json)
    invoice = _dict_to_invoice(json.loads(invoice_data))
    result = _risk(arithmetic, duplicate, vendor, policy, invoice)
    return result.model_dump_json()


@tool(
    name="detect_transaction_anomalies",
    description=(
        "Execute deterministic financial anomaly detection rules on an invoice against historical "
        "records. Detects recurring subscription price increases with percentage and dollar changes, "
        "duplicate billing, line-item arithmetic discrepancies, and unregistered vendor spend breaches. "
        "Returns a structured AnomalyScanReport."
    ),
)
def detect_transaction_anomalies(invoice_data: str, historical_invoices: str) -> str:
    """Run deterministic anomaly detection on invoice.

    Args:
        invoice_data: JSON string containing the invoice.
        historical_invoices: JSON string containing historical invoices list.

    Returns:
        JSON string of AnomalyScanReport.
    """
    inv = _dict_to_invoice(json.loads(invoice_data))
    history = [_dict_to_invoice(h) for h in json.loads(historical_invoices)]
    report = _anomaly(inv, history)
    return report.model_dump_json()


# Backward compatibility aliases
verify_invoice_arithmetic = calculate_invoice_arithmetic
check_invoice_duplicates = check_duplicate_invoice
get_vendor_history_tool = get_vendor_history
evaluate_invoice_policy_tool = evaluate_invoice_policy
calculate_invoice_risk_tool = calculate_invoice_risk
detect_transaction_anomalies_tool = detect_transaction_anomalies

# Ordered list of core LedgerGuard verification tools for Agent registration
LEDGERGUARD_TOOLS = [
    calculate_invoice_arithmetic,
    check_duplicate_invoice,
    get_vendor_history,
    evaluate_invoice_policy,
    calculate_invoice_risk,
]

# Extended catalogue including deterministic anomaly detection
EXTENDED_LEDGERGUARD_TOOLS = [
    *LEDGERGUARD_TOOLS,
    detect_transaction_anomalies,
]
