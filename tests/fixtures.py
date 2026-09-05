"""Synthetic test fixtures for LedgerGuard invoice verification suite.

Strictly synthetic data. No real entities, companies, or personal data.
Provides representative cases covering happy path, discrepancies, duplicates,
boundary values, incomplete extractions, and multi-currency scenarios.
"""

from datetime import date, timedelta
from decimal import Decimal

from app.models.invoice import Invoice, LineItem


def get_clean_invoice() -> Invoice:
    """Return standard compliant invoice with clean arithmetic and normal amounts."""
    return Invoice(
        invoice_id="INV-SYN-001",
        invoice_number="ACME-2026-001",
        vendor_id="VEND-ACME-01",
        vendor_name="Acme Industrial Supplies Ltd",
        customer_name="Global Enterprise Inc",
        invoice_date=date(2026, 3, 1),
        currency="USD",
        subtotal=Decimal("200.00"),
        tax=Decimal("20.00"),
        discount=Decimal("0.00"),
        total=Decimal("220.00"),
        line_items=[
            LineItem(
                description="Industrial Grade Widgets",
                quantity=Decimal("2"),
                unit_price=Decimal("100.00"),
                tax_rate=Decimal("10.00"),
                discount=Decimal("0.00"),
            )
        ],
    )


def get_arithmetic_mismatch_invoice() -> Invoice:
    """Return invoice where reported total deviates from calculated sum."""
    return Invoice(
        invoice_id="INV-SYN-002",
        invoice_number="ACME-2026-002",
        vendor_id="VEND-ACME-01",
        vendor_name="Acme Industrial Supplies Ltd",
        customer_name="Global Enterprise Inc",
        invoice_date=date(2026, 3, 2),
        currency="USD",
        subtotal=Decimal("200.00"),
        tax=Decimal("20.00"),
        discount=Decimal("0.00"),
        total=Decimal("250.00"),  # Expected is 220.00 -> 30.00 discrepancy
        line_items=[
            LineItem(
                description="Industrial Grade Widgets",
                quantity=Decimal("2"),
                unit_price=Decimal("100.00"),
                tax_rate=Decimal("10.00"),
                discount=Decimal("0.00"),
            )
        ],
    )


def get_historical_invoices() -> list[Invoice]:
    """Baseline historical invoices for duplicate and vendor history tests."""
    return [
        Invoice(
            invoice_id="HIST-001",
            invoice_number="ACME-2026-001",
            vendor_id="VEND-ACME-01",
            vendor_name="Acme Industrial Supplies Ltd",
            customer_name="Global Enterprise Inc",
            invoice_date=date(2026, 2, 1),
            currency="USD",
            subtotal=Decimal("200.00"),
            tax=Decimal("20.00"),
            discount=Decimal("0.00"),
            total=Decimal("220.00"),
            line_items=[
                LineItem(
                    description="Industrial Grade Widgets",
                    quantity=Decimal("2"),
                    unit_price=Decimal("100.00"),
                )
            ],
        ),
        Invoice(
            invoice_id="HIST-002",
            invoice_number="ACME-2026-005",
            vendor_id="VEND-ACME-01",
            vendor_name="Acme Industrial Supplies Ltd",
            customer_name="Global Enterprise Inc",
            invoice_date=date(2026, 2, 25),
            currency="USD",
            subtotal=Decimal("400.00"),
            tax=Decimal("40.00"),
            discount=Decimal("0.00"),
            total=Decimal("440.00"),
            line_items=[
                LineItem(
                    description="Heavy Duty Bolts",
                    quantity=Decimal("4"),
                    unit_price=Decimal("100.00"),
                )
            ],
        ),
    ]


def get_confirmed_duplicate_invoice() -> Invoice:
    """Candidate invoice matching both vendor_id and invoice_number of HIST-001."""
    return Invoice(
        invoice_id="INV-SYN-CONFIRMED-DUP",
        invoice_number="ACME-2026-001",  # Same number as HIST-001
        vendor_id="VEND-ACME-01",        # Same vendor as HIST-001
        vendor_name="Acme Industrial Supplies Ltd",
        customer_name="Global Enterprise Inc",
        invoice_date=date(2026, 3, 5),
        currency="USD",
        subtotal=Decimal("200.00"),
        tax=Decimal("20.00"),
        discount=Decimal("0.00"),
        total=Decimal("220.00"),
        line_items=[
            LineItem(
                description="Industrial Grade Widgets",
                quantity=Decimal("2"),
                unit_price=Decimal("100.00"),
            )
        ],
    )


def get_possible_duplicate_invoice() -> Invoice:
    """Candidate invoice matching vendor and amount within 4 days of HIST-002."""
    return Invoice(
        invoice_id="INV-SYN-POSSIBLE-DUP",
        invoice_number="ACME-2026-099",  # Different number
        vendor_id="VEND-ACME-01",        # Same vendor
        vendor_name="Acme Industrial Supplies Ltd",
        customer_name="Global Enterprise Inc",
        invoice_date=date(2026, 3, 1),   # 4 days after HIST-002 (Feb 25)
        currency="USD",
        subtotal=Decimal("400.00"),
        tax=Decimal("40.00"),
        discount=Decimal("0.00"),
        total=Decimal("440.00"),          # Same amount as HIST-002
        line_items=[
            LineItem(
                description="Heavy Duty Bolts",
                quantity=Decimal("4"),
                unit_price=Decimal("100.00"),
            )
        ],
    )


def get_new_vendor_invoice() -> Invoice:
    """Invoice from a vendor that does not appear in history."""
    return Invoice(
        invoice_id="INV-SYN-NEW-VEND",
        invoice_number="NOVA-9001",
        vendor_id="VEND-NOVA-99",
        vendor_name="Nova Tech Solutions Inc",
        customer_name="Global Enterprise Inc",
        invoice_date=date(2026, 3, 1),
        currency="USD",
        subtotal=Decimal("500.00"),
        tax=Decimal("50.00"),
        discount=Decimal("0.00"),
        total=Decimal("550.00"),
        line_items=[
            LineItem(
                description="Cloud Configuration Consulting",
                quantity=Decimal("5"),
                unit_price=Decimal("100.00"),
            )
        ],
    )


def get_high_value_invoice() -> Invoice:
    """Invoice with total >= $5000 (triggers high-value policy)."""
    return Invoice(
        invoice_id="INV-SYN-HIGH-VAL",
        invoice_number="ACME-2026-HV",
        vendor_id="VEND-ACME-01",
        vendor_name="Acme Industrial Supplies Ltd",
        customer_name="Global Enterprise Inc",
        invoice_date=date(2026, 3, 1),
        currency="USD",
        subtotal=Decimal("10000.00"),
        tax=Decimal("1000.00"),
        discount=Decimal("0.00"),
        total=Decimal("11000.00"),
        line_items=[
            LineItem(
                description="Heavy Machinery Generator",
                quantity=Decimal("1"),
                unit_price=Decimal("10000.00"),
            )
        ],
    )


def get_policy_violation_invoice() -> Invoice:
    """Invoice between $1000 and $5000 that exceeds auto-approval ceiling ($1000)."""
    return Invoice(
        invoice_id="INV-SYN-POL-VIOL",
        invoice_number="ACME-2026-PV",
        vendor_id="VEND-ACME-01",
        vendor_name="Acme Industrial Supplies Ltd",
        customer_name="Global Enterprise Inc",
        invoice_date=date(2026, 3, 1),
        currency="USD",
        subtotal=Decimal("2000.00"),
        tax=Decimal("200.00"),
        discount=Decimal("0.00"),
        total=Decimal("2200.00"),
        line_items=[
            LineItem(
                description="Bulk Workshop Hardware",
                quantity=Decimal("20"),
                unit_price=Decimal("100.00"),
            )
        ],
    )


def get_incomplete_invoice() -> Invoice:
    """Invoice with missing financial amounts, representing partial OCR extraction."""
    return Invoice(
        invoice_id="INV-SYN-INCOMPLETE",
        invoice_number="RAW-2026-UNKNOWN",
        vendor_id="VEND-RAW-00",
        vendor_name="Scanned Vendor Placeholder",
        customer_name="Global Enterprise Inc",
        invoice_date=date(2026, 3, 1),
        currency="USD",
        subtotal=None,
        tax=None,
        discount=None,
        total=None,
        line_items=[],
    )


def get_multi_currency_history() -> list[Invoice]:
    """Historical invoices spanning multiple currencies for multi-currency safety tests."""
    return [
        Invoice(
            invoice_id="MC-HIST-001",
            invoice_number="EUR-001",
            vendor_id="VEND-EUROPE-01",
            vendor_name="Continental Components GmbH",
            customer_name="Global Enterprise Inc",
            invoice_date=date(2026, 1, 15),
            currency="EUR",
            subtotal=Decimal("1000.00"),
            tax=Decimal("190.00"),
            discount=Decimal("0.00"),
            total=Decimal("1190.00"),
            line_items=[
                LineItem(
                    description="Precision Bearings",
                    quantity=Decimal("10"),
                    unit_price=Decimal("100.00"),
                )
            ],
        ),
        Invoice(
            invoice_id="MC-HIST-002",
            invoice_number="USD-001",
            vendor_id="VEND-EUROPE-01",
            vendor_name="Continental Components GmbH",
            customer_name="Global Enterprise Inc",
            invoice_date=date(2026, 2, 10),
            currency="USD",
            subtotal=Decimal("500.00"),
            tax=Decimal("50.00"),
            discount=Decimal("0.00"),
            total=Decimal("550.00"),
            line_items=[
                LineItem(
                    description="Standard Fasteners",
                    quantity=Decimal("5"),
                    unit_price=Decimal("100.00"),
                )
            ],
        ),
    ]


def get_boundary_invoice(amount: Decimal) -> Invoice:
    """Generate invoice with specific total for boundary testing."""
    return Invoice(
        invoice_id=f"INV-BOUND-{amount}",
        invoice_number=f"BOUND-{amount}",
        vendor_id="VEND-ACME-01",
        vendor_name="Acme Industrial Supplies Ltd",
        customer_name="Global Enterprise Inc",
        invoice_date=date(2026, 3, 1),
        currency="USD",
        subtotal=amount,
        tax=Decimal("0.00"),
        discount=Decimal("0.00"),
        total=amount,
        line_items=[
            LineItem(
                description="Custom Boundary Item",
                quantity=Decimal("1"),
                unit_price=amount,
            )
        ],
    )


def get_zero_tax_invoice() -> Invoice:
    """Invoice with exactly tax = Decimal('0.00')."""
    return Invoice(
        invoice_id="INV-ZERO-TAX",
        invoice_number="ACME-ZERO-TAX",
        vendor_id="VEND-ACME-01",
        vendor_name="Acme Industrial Supplies Ltd",
        customer_name="Global Enterprise Inc",
        invoice_date=date(2026, 3, 1),
        currency="USD",
        subtotal=Decimal("500.00"),
        tax=Decimal("0.00"),
        discount=Decimal("0.00"),
        total=Decimal("500.00"),
        line_items=[
            LineItem(
                description="Tax Exempt Supply",
                quantity=Decimal("5"),
                unit_price=Decimal("100.00"),
            )
        ],
    )


def get_zero_discount_invoice() -> Invoice:
    """Invoice with exactly discount = Decimal('0.00')."""
    return Invoice(
        invoice_id="INV-ZERO-DISC",
        invoice_number="ACME-ZERO-DISC",
        vendor_id="VEND-ACME-01",
        vendor_name="Acme Industrial Supplies Ltd",
        customer_name="Global Enterprise Inc",
        invoice_date=date(2026, 3, 1),
        currency="USD",
        subtotal=Decimal("300.00"),
        tax=Decimal("30.00"),
        discount=Decimal("0.00"),
        total=Decimal("330.00"),
        line_items=[
            LineItem(
                description="Standard Item",
                quantity=Decimal("3"),
                unit_price=Decimal("100.00"),
            )
        ],
    )


def get_multiple_violations_invoice() -> Invoice:
    """Invoice triggering new vendor, high value ($7500), and arithmetic mismatch."""
    return Invoice(
        invoice_id="INV-SYN-MULTI-VIOL",
        invoice_number="MULTI-7500",
        vendor_id="VEND-NEW-UNKNOWN",
        vendor_name="Unknown New Provider",
        customer_name="Global Enterprise Inc",
        invoice_date=date(2026, 3, 1),
        currency="USD",
        subtotal=Decimal("7000.00"),
        tax=Decimal("700.00"),
        discount=Decimal("0.00"),
        total=Decimal("8000.00"),  # Discrepancy: expected 7700.00
        line_items=[
            LineItem(
                description="High End Consulting",
                quantity=Decimal("7"),
                unit_price=Decimal("1000.00"),
            )
        ],
    )
