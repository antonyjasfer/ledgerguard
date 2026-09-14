"""Comprehensive unit and integration tests for LedgerGuard Enterprise Context,
Company Policy, Vendor Master, Approval Matrix, Risk Scoring, and Demo Scenarios.
"""

from datetime import date
from decimal import Decimal
import pytest
from fastapi.testclient import TestClient

from app.agent.decision_guard import validate_agent_decision
from app.agent.orchestrator import run_verification_workflow
from app.api.main import app
from app.models.decision import AgentDecision
from app.models.invoice import Invoice, LineItem
from app.models.policy import (
    ApprovalRoutingTier,
    PolicyConfig,
    evaluate_approval_matrix,
)
from app.models.verification import (
    ArithmeticVerificationResult,
    DuplicateCheckResult,
    DuplicateStatus,
    PolicyVerificationResult,
    PolicyViolation,
    RecommendedAction,
    RiskLevel,
    VendorHistoryResult,
    VerificationStatus,
)
from app.services.vendor_context import (
    DEMO_VENDOR_MASTER,
    VendorContextService,
    vendor_context_service,
)
from app.tools.policy import evaluate_invoice_policy
from app.tools.risk import RiskWeights, calculate_invoice_risk


@pytest.fixture
def enterprise_policy() -> PolicyConfig:
    return PolicyConfig.get_demo_enterprise_policy()


@pytest.fixture
def clean_arithmetic() -> ArithmeticVerificationResult:
    return ArithmeticVerificationResult(
        passed=True,
        status=VerificationStatus.PASS,
        expected_total=Decimal("850.00"),
        actual_total=Decimal("850.00"),
        difference=Decimal("0.00"),
    )


@pytest.fixture
def no_duplicate() -> DuplicateCheckResult:
    return DuplicateCheckResult(
        status=DuplicateStatus.NO_DUPLICATE,
        matched_invoice_ids=[],
    )


def test_demo_enterprise_policy_configuration():
    """Verify company policy defaults and constraints."""
    policy = PolicyConfig.get_demo_enterprise_policy()
    assert policy.company_id == "LEDGERGUARD-DEMO"
    assert policy.company_name == "LedgerGuard Demo Corporation"
    assert policy.auto_approval_limit == Decimal("5000.00")
    assert policy.high_value_threshold == Decimal("25000.00")
    assert "USD" in policy.supported_currencies
    assert "EUR" in policy.supported_currencies
    assert "GBP" in policy.supported_currencies
    assert policy.arithmetic_mismatch_requires_block is True
    assert policy.new_vendor_requires_review is True
    assert policy.duplicate_requires_block is True
    assert policy.maximum_discount_percent == Decimal("20.00")


def test_policy_no_float_validation():
    """Ensure floating-point assignments in policy are strictly rejected."""
    with pytest.raises(TypeError, match="Floating-point values are forbidden"):
        PolicyConfig(auto_approval_limit=5000.0)  # type: ignore

    with pytest.raises(TypeError, match="Floating-point values are forbidden"):
        PolicyConfig(maximum_discount_percent=20.5)  # type: ignore


def test_approval_matrix_tiers(enterprise_policy):
    """Verify deterministic routing through corporate approval matrix."""
    # Under $5,000 -> AUTO_APPROVAL_ALLOWED
    res1 = evaluate_approval_matrix(Decimal("850.00"), enterprise_policy)
    assert res1.tier == ApprovalRoutingTier.AUTO_APPROVAL_ALLOWED

    # Exactly $5,000.00 -> AUTO_APPROVAL_ALLOWED
    res2 = evaluate_approval_matrix(Decimal("5000.00"), enterprise_policy)
    assert res2.tier == ApprovalRoutingTier.AUTO_APPROVAL_ALLOWED

    # $5,000.01 to $25,000.00 -> MANAGER_REVIEW
    res3 = evaluate_approval_matrix(Decimal("5000.01"), enterprise_policy)
    assert res3.tier == ApprovalRoutingTier.MANAGER_REVIEW

    # $25,000.01+ -> FINANCE_DIRECTOR_REVIEW
    res4 = evaluate_approval_matrix(Decimal("40000.00"), enterprise_policy)
    assert res4.tier == ApprovalRoutingTier.FINANCE_DIRECTOR_REVIEW

    # Confirmed duplicate -> BLOCK
    res5 = evaluate_approval_matrix(Decimal("500.00"), enterprise_policy, is_duplicate=True)
    assert res5.tier == ApprovalRoutingTier.BLOCK

    # Arithmetic mismatch with policy block -> BLOCK
    res6 = evaluate_approval_matrix(Decimal("500.00"), enterprise_policy, has_arithmetic_mismatch=True)
    assert res6.tier == ApprovalRoutingTier.BLOCK

    # New vendor -> MANUAL_REVIEW
    res7 = evaluate_approval_matrix(Decimal("500.00"), enterprise_policy, is_new_vendor=True)
    assert res7.tier == ApprovalRoutingTier.MANUAL_REVIEW


def test_vendor_master_dataset():
    """Verify synthetic vendor master contains required vendors."""
    vendors = vendor_context_service.list_vendors()
    vendor_ids = {v.vendor_id for v in vendors}
    assert "SUPERSTORE-001" in vendor_ids
    assert "APEX-001" in vendor_ids
    assert "NOVA-001" in vendor_ids
    assert "NORTHSTAR-001" in vendor_ids
    assert "MERIDIAN-001" in vendor_ids
    assert "NEW-VENDOR-001" in vendor_ids

    # Verify lookups by ID, name, and alias
    superstore = vendor_context_service.get_vendor("SUPERSTORE-001")
    assert superstore is not None
    assert superstore.legal_name == "SuperStore"
    assert superstore.po_required is True
    assert superstore.bank_verification_status == "VERIFIED"
    assert superstore.historical_invoice_count == 127

    # Alias lookup
    by_alias = vendor_context_service.get_vendor("super store")
    assert by_alias is not None
    assert by_alias.vendor_id == "SUPERSTORE-001"


def test_vendor_context_deviation_calculation():
    """Verify amount deviation factor vs historical average."""
    inv = Invoice(
        invoice_id="DEV-001",
        invoice_number="INV-DEV-001",
        vendor_id="SUPERSTORE-001",
        vendor_name="SuperStore",
        customer_name="Demo Corp",
        invoice_date=date(2026, 9, 1),
        currency="USD",
        subtotal=Decimal("5000.00"),
        discount=Decimal("0.00"),
        shipping=Decimal("0.00"),
        tax=Decimal("0.00"),
        total=Decimal("5000.00"),
        line_items=[LineItem(description="Item", quantity=Decimal("1"), unit_price=Decimal("5000.00"))],
    )
    ctx = vendor_context_service.evaluate_vendor_context(inv)
    assert ctx.vendor_exists is True
    assert ctx.historical_average == Decimal("1242.52")
    # Deviation = 5000 / 1242.52 = 4.02x
    assert ctx.deviation_factor == Decimal("4.02")
    assert ctx.is_above_normal_range is False  # normal max is 5000.00

    # Above normal range invoice
    inv_high = Invoice(
        invoice_id="DEV-002",
        invoice_number="INV-DEV-002",
        vendor_id="SUPERSTORE-001",
        vendor_name="SuperStore",
        customer_name="Demo Corp",
        invoice_date=date(2026, 9, 1),
        currency="USD",
        subtotal=Decimal("7500.00"),
        discount=Decimal("0.00"),
        shipping=Decimal("0.00"),
        tax=Decimal("0.00"),
        total=Decimal("7500.00"),
        line_items=[LineItem(description="Item", quantity=Decimal("1"), unit_price=Decimal("7500.00"))],
    )
    ctx_high = vendor_context_service.evaluate_vendor_context(inv_high)
    assert ctx_high.is_above_normal_range is True


def test_vendor_context_new_vendor():
    """Verify new vendor has neutral deviation and no faked history."""
    inv = Invoice(
        invoice_id="NV-001",
        invoice_number="INV-NV-001",
        vendor_id="NEW-VENDOR-001",
        vendor_name="New Unverified Supplies LLC",
        customer_name="Demo Corp",
        invoice_date=date(2026, 9, 1),
        currency="USD",
        subtotal=Decimal("850.00"),
        discount=Decimal("0.00"),
        shipping=Decimal("0.00"),
        tax=Decimal("0.00"),
        total=Decimal("850.00"),
        line_items=[LineItem(description="Item", quantity=Decimal("1"), unit_price=Decimal("850.00"))],
    )
    ctx = vendor_context_service.evaluate_vendor_context(inv)
    assert ctx.is_new_vendor is True
    assert ctx.historical_invoice_count == 0
    assert ctx.deviation_factor is None
    assert ctx.bank_verification_status == "NOT_VERIFIED"


def test_vendor_context_currency_and_po():
    """Verify currency validation and PO requirement detection."""
    inv_unsupported_curr = Invoice(
        invoice_id="CURR-001",
        invoice_number="INV-CURR-001",
        vendor_id="SUPERSTORE-001",
        vendor_name="SuperStore",
        customer_name="Demo Corp",
        invoice_date=date(2026, 9, 1),
        currency="EUR",  # SuperStore approved only for USD
        subtotal=Decimal("100.00"),
        discount=Decimal("0.00"),
        shipping=Decimal("0.00"),
        tax=Decimal("0.00"),
        total=Decimal("100.00"),
        line_items=[LineItem(description="Item", quantity=Decimal("1"), unit_price=Decimal("100.00"))],
    )
    ctx = vendor_context_service.evaluate_vendor_context(inv_unsupported_curr)
    assert ctx.currency_supported is False
    assert ctx.po_required is True
    assert ctx.missing_po is True


def test_scenario_1_clean_established_vendor():
    """Scenario 1: SuperStore, $850, established history, clean arithmetic -> AUTO_APPROVE."""
    inv = Invoice(
        invoice_id="SCENARIO-1",
        invoice_number="INV-S1-001",
        vendor_id="SUPERSTORE-001",
        vendor_name="SuperStore",
        customer_name="LedgerGuard Demo Corp",
        invoice_date=date(2026, 9, 10),
        currency="USD",
        subtotal=Decimal("850.00"),
        discount=Decimal("0.00"),
        shipping=Decimal("0.00"),
        tax=Decimal("0.00"),
        total=Decimal("850.00"),
        purchase_order_number="PO-2026-9901",
        line_items=[LineItem(description="Office Furniture", quantity=Decimal("1"), unit_price=Decimal("850.00"))],
    )
    policy = PolicyConfig.get_demo_enterprise_policy()
    decision, meta = run_verification_workflow(inv, policy_config=policy)

    assert decision.decision == AgentDecision.AUTO_APPROVE
    assert decision.risk_level == RiskLevel.LOW
    assert decision.requires_human is False


def test_scenario_2_new_vendor():
    """Scenario 2: NEW-VENDOR-001, $850 -> MANUAL_REVIEW."""
    inv = Invoice(
        invoice_id="SCENARIO-2",
        invoice_number="INV-S2-001",
        vendor_id="NEW-VENDOR-001",
        vendor_name="New Unverified Supplies LLC",
        customer_name="LedgerGuard Demo Corp",
        invoice_date=date(2026, 9, 10),
        currency="USD",
        subtotal=Decimal("850.00"),
        discount=Decimal("0.00"),
        shipping=Decimal("0.00"),
        tax=Decimal("0.00"),
        total=Decimal("850.00"),
        purchase_order_number="PO-2026-9902",
        line_items=[LineItem(description="Lab Equipment", quantity=Decimal("1"), unit_price=Decimal("850.00"))],
    )
    policy = PolicyConfig.get_demo_enterprise_policy()
    decision, meta = run_verification_workflow(inv, policy_config=policy)

    assert decision.decision == AgentDecision.MANUAL_REVIEW
    assert decision.requires_human is True
    assert decision.risk_level in (RiskLevel.MEDIUM, RiskLevel.HIGH)


def test_scenario_3_high_value():
    """Scenario 3: SuperStore, $40,000 invoice exceeds $25,000 threshold -> MANUAL_REVIEW / ESCALATE."""
    inv = Invoice(
        invoice_id="SCENARIO-3",
        invoice_number="INV-S3-001",
        vendor_id="SUPERSTORE-001",
        vendor_name="SuperStore",
        customer_name="LedgerGuard Demo Corp",
        invoice_date=date(2026, 9, 10),
        currency="USD",
        subtotal=Decimal("40000.00"),
        discount=Decimal("0.00"),
        shipping=Decimal("0.00"),
        tax=Decimal("0.00"),
        total=Decimal("40000.00"),
        purchase_order_number="PO-2026-9903",
        line_items=[LineItem(description="Bulk Inventory", quantity=Decimal("40"), unit_price=Decimal("1000.00"))],
    )
    policy = PolicyConfig.get_demo_enterprise_policy()
    decision, meta = run_verification_workflow(inv, policy_config=policy)

    assert decision.decision == AgentDecision.MANUAL_REVIEW
    assert decision.requires_human is True
    assert decision.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL)


def test_scenario_4_confirmed_duplicate():
    """Scenario 4: Duplicate invoice number from same vendor -> BLOCK, CRITICAL."""
    prior = Invoice(
        invoice_id="HIST-DUP-01",
        invoice_number="INV-DUP-100",
        vendor_id="SUPERSTORE-001",
        vendor_name="SuperStore",
        customer_name="LedgerGuard Demo Corp",
        invoice_date=date(2026, 9, 1),
        currency="USD",
        subtotal=Decimal("850.00"),
        discount=Decimal("0.00"),
        shipping=Decimal("0.00"),
        tax=Decimal("0.00"),
        total=Decimal("850.00"),
        purchase_order_number="PO-2026-9904",
        line_items=[LineItem(description="Supplies", quantity=Decimal("1"), unit_price=Decimal("850.00"))],
    )
    candidate = Invoice(
        invoice_id="SCENARIO-4",
        invoice_number="INV-DUP-100",
        vendor_id="SUPERSTORE-001",
        vendor_name="SuperStore",
        customer_name="LedgerGuard Demo Corp",
        invoice_date=date(2026, 9, 10),
        currency="USD",
        subtotal=Decimal("850.00"),
        discount=Decimal("0.00"),
        shipping=Decimal("0.00"),
        tax=Decimal("0.00"),
        total=Decimal("850.00"),
        purchase_order_number="PO-2026-9904",
        line_items=[LineItem(description="Supplies", quantity=Decimal("1"), unit_price=Decimal("850.00"))],
    )
    policy = PolicyConfig.get_demo_enterprise_policy()
    decision, meta = run_verification_workflow(candidate, history=[prior], policy_config=policy)

    assert decision.decision == AgentDecision.BLOCK
    assert decision.risk_level == RiskLevel.CRITICAL
    assert decision.risk_score == 100


def test_scenario_5_arithmetic_mismatch_blocks_under_enterprise_policy():
    """Scenario 5: Declared total differs from calculated total -> BLOCK under demo policy."""
    inv = Invoice(
        invoice_id="SCENARIO-5",
        invoice_number="INV-S5-001",
        vendor_id="SUPERSTORE-001",
        vendor_name="SuperStore",
        customer_name="LedgerGuard Demo Corp",
        invoice_date=date(2026, 9, 10),
        currency="USD",
        subtotal=Decimal("500.00"),
        discount=Decimal("0.00"),
        shipping=Decimal("0.00"),
        tax=Decimal("0.00"),
        total=Decimal("999.00"),  # arithmetic discrepancy of 499.00
        purchase_order_number="PO-2026-9905",
        line_items=[LineItem(description="Item", quantity=Decimal("5"), unit_price=Decimal("100.00"))],
    )
    policy = PolicyConfig.get_demo_enterprise_policy()
    decision, meta = run_verification_workflow(inv, policy_config=policy)

    assert decision.decision == AgentDecision.BLOCK
    assert decision.requires_human is True


def test_real_superstore_invoice_36259():
    """Verify exact real SuperStore invoice #36259 calculation: 53.82 - 0 + 4.29 + 0 = 58.11."""
    inv = Invoice(
        invoice_id="DEMO-SUPERSTORE-36259",
        invoice_number="36259",
        vendor_id="SUPERSTORE-001",
        vendor_name="SuperStore",
        customer_name="LedgerGuard Demo Corp",
        invoice_date=date(2012, 3, 6),
        currency="USD",
        subtotal=Decimal("53.82"),
        discount=Decimal("0.00"),
        shipping=Decimal("4.29"),
        tax=Decimal("0.00"),
        total=Decimal("58.11"),
        purchase_order_number="PO-36259",
        line_items=[
            LineItem(description="Newell 330", quantity=Decimal("1"), unit_price=Decimal("53.82")),
        ],
    )
    policy = PolicyConfig.get_demo_enterprise_policy()
    decision, meta = run_verification_workflow(inv, policy_config=policy)

    assert decision.decision == AgentDecision.AUTO_APPROVE
    assert decision.risk_level == RiskLevel.LOW
    assert decision.risk_score == 0


def test_enterprise_api_routes():
    """Verify REST endpoints for /policy, /vendors, and /vendors/{id}."""
    client = TestClient(app)

    # 1. GET /policy
    policy_resp = client.get("/policy")
    assert policy_resp.status_code == 200
    data = policy_resp.json()
    assert data["company_id"] == "LEDGERGUARD-DEMO"
    assert data["company_name"] == "LedgerGuard Demo Corporation"
    assert Decimal(str(data["auto_approval_limit"])) == Decimal("5000.00")
    assert Decimal(str(data["high_value_threshold"])) == Decimal("25000.00")
    assert len(data["approval_matrix_tiers"]) > 0

    # 2. GET /vendors
    vendors_resp = client.get("/vendors")
    assert vendors_resp.status_code == 200
    v_data = vendors_resp.json()
    assert v_data["total"] >= 6
    vendor_ids = [item["vendor_id"] for item in v_data["items"]]
    assert "SUPERSTORE-001" in vendor_ids

    # 3. GET /vendors/SUPERSTORE-001
    single_resp = client.get("/vendors/SUPERSTORE-001")
    assert single_resp.status_code == 200
    s_data = single_resp.json()
    assert s_data["legal_name"] == "SuperStore"
    assert s_data["historical_invoice_count"] == 127
    assert s_data["bank_verification_status"] == "VERIFIED"

    # 4. GET /vendors/NONEXISTENT -> 404
    missing_resp = client.get("/vendors/NONEXISTENT-999")
    assert missing_resp.status_code == 404
