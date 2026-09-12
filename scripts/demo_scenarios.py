"""Synthetic demo scenario generator for LedgerGuard Phase 6.

Produces deterministic synthetic test cases:
1. Scenario 1: CLEAN -> AUTO_APPROVED
   - Established vendor, accurate math, below threshold, zero duplicate collision.
2. Scenario 2: RISKY -> MANUAL_REVIEW
   - High total amount, new vendor profile, policy warning, requires human audit.
3. Scenario 3: DUPLICATE / CRITICAL RISK -> Decision Guard -> BLOCKED
   - Duplicate invoice collision or critical risk threshold, Decision Guard forces BLOCK.

All invoices use strictly synthetic identifiers and data.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


from decimal import Decimal
from datetime import date, datetime, timezone
from typing import Any

from app.models.invoice import Invoice, LineItem
from app.models.policy import PolicyConfig


def get_scenario_1_clean() -> dict[str, Any]:
    """Scenario 1: Clean invoice resulting in AUTO_APPROVED verdict."""
    return {
        "invoice_id": "DEMO-INV-CLEAN-01",
        "invoice_number": "INV-2026-001",
        "vendor_id": "VEND-APEX",
        "vendor_name": "Apex Cloud Technologies LLC",
        "invoice_date": "2026-03-01",
        "currency": "USD",
        "customer_name": "Global Enterprise Inc",
        "subtotal": 500.00,
        "tax": 50.00,
        "discount": 0.00,
        "total": 550.00,
        "line_items": [
            {
                "item_id": "ITEM-101",
                "description": "Enterprise Cloud API Tier 1 Subscription",
                "quantity": 1,
                "unit_price": 500.00,
                "amount": 500.00,
            },
        ],
    }


def get_scenario_2_risky() -> dict[str, Any]:
    """Scenario 2: Risky invoice resulting in MANUAL_REVIEW verdict."""
    return {
        "invoice_id": "DEMO-INV-RISKY-02",
        "invoice_number": "INV-2026-999",
        "vendor_id": "VEND-NOVA-NEW",
        "vendor_name": "Nova Advisory Partners Inc",
        "invoice_date": "2026-03-02",
        "currency": "USD",
        "customer_name": "Global Enterprise Inc",
        "subtotal": 55000.00,
        "tax": 5500.00,
        "discount": 0.00,
        "total": 60500.00,
        "line_items": [
            {
                "item_id": "ITEM-201",
                "description": "Strategic Cloud Architecture Overhaul Consulting",
                "quantity": 1,
                "unit_price": 55000.00,
                "amount": 55000.00,
            }
        ],
    }


def get_scenario_3_blocked(duplicate_of: str = "INV-2026-001") -> dict[str, Any]:
    """Scenario 3: Duplicate / Critical Risk resulting in Decision Guard -> BLOCKED."""
    return {
        "invoice_id": "DEMO-INV-BLOCK-03",
        "invoice_number": duplicate_of,  # Exact duplicate invoice number for same vendor
        "vendor_id": "VEND-APEX",
        "vendor_name": "Apex Cloud Technologies LLC",
        "invoice_date": "2026-03-03",
        "currency": "USD",
        "customer_name": "Global Enterprise Inc",
        "subtotal": 500.00,
        "tax": 50.00,
        "discount": 0.00,
        "total": 550.00,
        "line_items": [
            {
                "item_id": "ITEM-101",
                "description": "Duplicate Enterprise Cloud API Tier 1 Subscription",
                "quantity": 1,
                "unit_price": 500.00,
                "amount": 500.00,
            },
        ],
    }


def get_all_scenarios() -> list[dict[str, Any]]:
    """Return all 3 synthetic demo scenarios."""
    return [
        get_scenario_1_clean(),
        get_scenario_2_risky(),
        get_scenario_3_blocked(),
    ]
