"""Tests for LedgerGuard Agent orchestration and decision routing across scenarios.

Verifies end-to-end deterministic orchestration for all core business scenarios:
- Scenario A: Clean invoice -> AUTO_APPROVE
- Scenario B: Confirmed duplicate -> BLOCK
- Scenario C: Arithmetic mismatch -> MANUAL_REVIEW
- Scenario D: New vendor + high value -> MANUAL_REVIEW
- Scenario E: Insufficient evidence -> MANUAL_REVIEW
- Decision Guard override on conflicting agent proposal
- Tool execution trace tracking
- Safe execution metadata observability
"""

from datetime import date
from decimal import Decimal
import pytest

from app.agent.orchestrator import ExecutionMetadata, run_verification_workflow
from app.models.decision import AgentDecision, VerificationDecision
from app.models.invoice import Invoice, LineItem
from app.models.verification import RiskLevel


def _create_base_invoice(
    invoice_id="INV-TEST-001",
    invoice_number="INV-2025-001",
    vendor_id="VEND-100",
    vendor_name="Acme Supplies",
    customer_name="LedgerGuard Corp",
    invoice_date=date(2025, 6, 1),
    subtotal=Decimal("500.00"),
    tax=Decimal("25.00"),
    discount=Decimal("0.00"),
    total=Decimal("525.00"),
    quantity=Decimal("5"),
    unit_price=Decimal("100.00"),
) -> Invoice:
    return Invoice(
        invoice_id=invoice_id,
        invoice_number=invoice_number,
        vendor_id=vendor_id,
        vendor_name=vendor_name,
        customer_name=customer_name,
        invoice_date=invoice_date,
        currency="USD",
        subtotal=subtotal,
        tax=tax,
        discount=discount,
        total=total,
        line_items=[
            LineItem(
                description="Standard Test Widget",
                quantity=quantity,
                unit_price=unit_price,
            )
        ],
    )


class TestAgentOrchestrationScenarios:
    """Scenario-based end-to-end verification tests."""

    def test_scenario_a_clean_invoice_auto_approve(self):
        """Scenario A: Clean invoice, established vendor, all checks pass -> AUTO_APPROVE."""
        # Established vendor history (5 past invoices)
        history = [
            _create_base_invoice(
                invoice_id=f"HIST-{i}",
                invoice_number=f"INV-PAST-{i}",
                invoice_date=date(2025, 1 + i, 1),
            )
            for i in range(5)
        ]

        candidate = _create_base_invoice(
            invoice_id="NEW-INV-001",
            invoice_number="INV-NEW-001",
        )

        decision, meta = run_verification_workflow(candidate, history)

        assert decision.decision == AgentDecision.AUTO_APPROVE
        assert decision.requires_human is False
        assert meta.decision == AgentDecision.AUTO_APPROVE
        assert meta.was_overridden is False
        assert len(meta.tools_called) == 5
        assert "calculate_invoice_arithmetic" in meta.tools_called
        assert "check_duplicate_invoice" in meta.tools_called
        assert "get_vendor_history" in meta.tools_called
        assert "evaluate_invoice_policy" in meta.tools_called
        assert "calculate_invoice_risk" in meta.tools_called

    def test_scenario_b_confirmed_duplicate_block(self):
        """Scenario B: Confirmed duplicate (same vendor + invoice_number) -> BLOCK."""
        history = [
            _create_base_invoice(
                invoice_id="ORIGINAL-INV",
                invoice_number="INV-DUP-100",
                vendor_id="VEND-100",
            )
        ]

        # Different invoice_id but same vendor_id and invoice_number
        candidate = _create_base_invoice(
            invoice_id="CANDIDATE-INV",
            invoice_number="INV-DUP-100",
            vendor_id="VEND-100",
        )

        decision, meta = run_verification_workflow(candidate, history)

        assert decision.decision == AgentDecision.BLOCK
        assert decision.requires_human is True
        assert meta.decision == AgentDecision.BLOCK
        assert "check_duplicate_invoice" in meta.tools_called

    def test_scenario_c_arithmetic_mismatch_manual_review(self):
        """Scenario C: Arithmetic calculation mismatch -> MANUAL_REVIEW."""
        history = [
            _create_base_invoice(
                invoice_id=f"HIST-{i}",
                invoice_number=f"INV-PAST-{i}",
            )
            for i in range(5)
        ]

        # Line items sum to 500.00 + 25.00 = 525.00, but invoice claims total is 999.00
        candidate = _create_base_invoice(
            invoice_id="ARITH-MISMATCH",
            invoice_number="INV-ARITH-001",
            total=Decimal("999.00"),
        )

        decision, meta = run_verification_workflow(candidate, history)

        assert decision.decision == AgentDecision.MANUAL_REVIEW
        assert decision.requires_human is True
        assert meta.decision == AgentDecision.MANUAL_REVIEW

    def test_scenario_d_new_vendor_high_value_manual_review(self):
        """Scenario D: New vendor with high-value invoice ($6,000) -> MANUAL_REVIEW."""
        # Empty history -> New vendor
        history = []

        candidate = _create_base_invoice(
            invoice_id="NEW-VEND-HIGH",
            invoice_number="INV-NV-001",
            vendor_id="VEND-NEW-999",
            quantity=Decimal("6"),
            unit_price=Decimal("1000.00"),
            subtotal=Decimal("6000.00"),
            tax=Decimal("0.00"),
            discount=Decimal("0.00"),
            total=Decimal("6000.00"),
        )

        decision, meta = run_verification_workflow(candidate, history)

        assert decision.decision == AgentDecision.MANUAL_REVIEW
        assert decision.requires_human is True
        assert meta.decision == AgentDecision.MANUAL_REVIEW

    def test_scenario_e_insufficient_evidence_manual_review(self):
        """Scenario E: Incomplete invoice data without line items or subtotal -> MANUAL_REVIEW."""
        history = [
            _create_base_invoice(
                invoice_id=f"HIST-{i}",
                invoice_number=f"INV-PAST-{i}",
            )
            for i in range(5)
        ]

        candidate = Invoice(
            invoice_id="INCOMPLETE-001",
            invoice_number="INV-INC-001",
            vendor_id="VEND-100",
            vendor_name="Acme Supplies",
            customer_name="LedgerGuard Corp",
            invoice_date=date(2025, 6, 1),
            currency="USD",
            total=Decimal("500.00"),
            line_items=[],
        )

        decision, meta = run_verification_workflow(candidate, history=history)

        assert decision.decision == AgentDecision.MANUAL_REVIEW
        assert decision.requires_human is True
        assert meta.decision == AgentDecision.MANUAL_REVIEW


class TestDecisionGuardInOrchestration:
    """Test Decision Guard overrides in full workflow."""

    def test_guard_overrides_hallucinated_auto_approve_on_duplicate(self):
        """If an agent proposes AUTO_APPROVE for a duplicate, Guard forces BLOCK."""
        history = [
            _create_base_invoice(
                invoice_id="HIST-DUP",
                invoice_number="INV-DUP-999",
                vendor_id="VEND-100",
            )
        ]
        candidate = _create_base_invoice(
            invoice_id="CANDIDATE-DUP",
            invoice_number="INV-DUP-999",
            vendor_id="VEND-100",
        )

        decision, meta = run_verification_workflow(
            candidate,
            history,
            agent_proposed_decision=AgentDecision.AUTO_APPROVE,
        )

        assert decision.decision == AgentDecision.BLOCK
        assert meta.was_overridden is True
        assert "CONFIRMED_DUPLICATE" in meta.override_reason


class TestObservabilityAndToolTrace:
    """Test audit trace and safe execution metadata."""

    def test_metadata_excludes_secrets_and_contains_required_fields(self):
        """Metadata includes run ID, provider, model, tools_called, decision."""
        candidate = _create_base_invoice(invoice_id="OBS-001")
        decision, meta = run_verification_workflow(candidate)

        assert meta.agent_run_id.startswith("run_")
        assert meta.provider is not None
        assert meta.model is not None
        assert isinstance(meta.tools_called, list)
        assert meta.decision in (AgentDecision.AUTO_APPROVE, AgentDecision.MANUAL_REVIEW, AgentDecision.BLOCK)

        # Check serialization safety: no secret field names
        meta_dict = meta.model_dump()
        meta_str = str(meta_dict)
        assert "secret" not in meta_str.lower()
        assert "token" not in meta_str.lower()
        assert "password" not in meta_str.lower()
        assert "key" not in meta_str.lower() or "risk_score" in meta_str
