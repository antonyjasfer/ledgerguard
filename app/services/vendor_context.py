"""Deterministic Vendor Master and Context Service for LedgerGuard.

Provides authoritative synthetic vendor profiles, historical metrics,
and invoice-vs-vendor context comparisons. Zero LLM reliance.
"""

from decimal import Decimal
from typing import Sequence

from app.models.invoice import Invoice, MONEY_QUANTUM, ROUNDING_STRATEGY
from app.models.vendor import VendorRecord
from app.models.verification import VendorContextResult, VendorHistoryResult


# Authoritative synthetic vendor master dataset
DEMO_VENDOR_MASTER: list[VendorRecord] = [
    VendorRecord(
        vendor_id="SUPERSTORE-001",
        legal_name="SuperStore",
        status="ACTIVE",
        country="US",
        approved_currencies=["USD"],
        payment_terms="Net 30",
        po_required=True,
        onboarding_status="APPROVED",
        bank_verification_status="VERIFIED",
        created_at="2023-01-15T00:00:00Z",
        historical_invoice_count=127,
        historical_total_spend=Decimal("157800.00"),
        historical_average_invoice=Decimal("1242.52"),
        historical_largest_invoice=Decimal("7800.00"),
        normal_invoice_min=Decimal("100.00"),
        normal_invoice_max=Decimal("5000.00"),
        aliases=["superstore", "superstore-001", "super store", "superstore inc"],
    ),
    VendorRecord(
        vendor_id="APEX-001",
        legal_name="Apex Cloud Technologies LLC",
        status="ACTIVE",
        country="US",
        approved_currencies=["USD", "EUR"],
        payment_terms="Net 15",
        po_required=True,
        onboarding_status="APPROVED",
        bank_verification_status="VERIFIED",
        created_at="2023-03-10T00:00:00Z",
        historical_invoice_count=84,
        historical_total_spend=Decimal("345000.00"),
        historical_average_invoice=Decimal("4107.14"),
        historical_largest_invoice=Decimal("18500.00"),
        normal_invoice_min=Decimal("500.00"),
        normal_invoice_max=Decimal("15000.00"),
        aliases=["apex", "apex cloud", "apex-001", "apex cloud technologies"],
    ),
    VendorRecord(
        vendor_id="NOVA-001",
        legal_name="Nova Advisory Partners Inc",
        status="ACTIVE",
        country="US",
        approved_currencies=["USD", "GBP"],
        payment_terms="Net 30",
        po_required=False,
        onboarding_status="APPROVED",
        bank_verification_status="VERIFIED",
        created_at="2023-06-01T00:00:00Z",
        historical_invoice_count=42,
        historical_total_spend=Decimal("134400.00"),
        historical_average_invoice=Decimal("3200.00"),
        historical_largest_invoice=Decimal("12000.00"),
        normal_invoice_min=Decimal("500.00"),
        normal_invoice_max=Decimal("15000.00"),
        aliases=["nova", "nova-001", "nova advisory", "nova advisory partners"],
    ),
    VendorRecord(
        vendor_id="NORTHSTAR-001",
        legal_name="Northstar Office Systems Ltd",
        status="ACTIVE",
        country="GB",
        approved_currencies=["GBP", "EUR", "USD"],
        payment_terms="Net 45",
        po_required=True,
        onboarding_status="APPROVED",
        bank_verification_status="VERIFIED",
        created_at="2023-08-20T00:00:00Z",
        historical_invoice_count=19,
        historical_total_spend=Decimal("41800.00"),
        historical_average_invoice=Decimal("2200.00"),
        historical_largest_invoice=Decimal("6500.00"),
        normal_invoice_min=Decimal("200.00"),
        normal_invoice_max=Decimal("6000.00"),
        aliases=["northstar", "northstar-001", "northstar office", "northstar office systems"],
    ),
    VendorRecord(
        vendor_id="MERIDIAN-001",
        legal_name="Meridian Industrial Supply Co",
        status="ACTIVE",
        country="US",
        approved_currencies=["USD"],
        payment_terms="Net 30",
        po_required=True,
        onboarding_status="APPROVED",
        bank_verification_status="VERIFIED",
        created_at="2023-11-05T00:00:00Z",
        historical_invoice_count=58,
        historical_total_spend=Decimal("92800.00"),
        historical_average_invoice=Decimal("1600.00"),
        historical_largest_invoice=Decimal("5500.00"),
        normal_invoice_min=Decimal("200.00"),
        normal_invoice_max=Decimal("5000.00"),
        aliases=["meridian", "meridian-001", "meridian industrial", "meridian supply"],
    ),
    VendorRecord(
        vendor_id="NEW-VENDOR-001",
        legal_name="New Unverified Supplies LLC",
        status="PENDING",
        country="US",
        approved_currencies=["USD"],
        payment_terms="Due on Receipt",
        po_required=True,
        onboarding_status="PENDING",
        bank_verification_status="NOT_VERIFIED",
        created_at="2026-09-01T00:00:00Z",
        historical_invoice_count=0,
        historical_total_spend=Decimal("0.00"),
        historical_average_invoice=Decimal("0.00"),
        historical_largest_invoice=Decimal("0.00"),
        normal_invoice_min=Decimal("0.00"),
        normal_invoice_max=Decimal("0.00"),
        aliases=["new-vendor-001", "new vendor", "new unverified supplies"],
    ),
    # Pre-existing test vendor profile for backward compatibility
    VendorRecord(
        vendor_id="VEND-100",
        legal_name="Acme Supplies",
        status="ACTIVE",
        country="US",
        approved_currencies=["USD"],
        payment_terms="Net 30",
        po_required=False,
        onboarding_status="APPROVED",
        bank_verification_status="VERIFIED",
        created_at="2024-01-01T00:00:00Z",
        historical_invoice_count=15,
        historical_total_spend=Decimal("15000.00"),
        historical_average_invoice=Decimal("1000.00"),
        historical_largest_invoice=Decimal("3000.00"),
        normal_invoice_min=Decimal("100.00"),
        normal_invoice_max=Decimal("3000.00"),
        aliases=["vend-100", "acme supplies", "vend-acme-01", "acme"],
    ),
]


class VendorContextService:
    """Deterministic service for querying vendor master profiles and evaluating context."""

    def __init__(self, vendors: list[VendorRecord] | None = None) -> None:
        self._vendors = list(vendors if vendors is not None else DEMO_VENDOR_MASTER)
        self._vendor_map: dict[str, VendorRecord] = {}
        self._reindex()

    def _reindex(self) -> None:
        self._vendor_map.clear()
        for v in self._vendors:
            self._vendor_map[v.vendor_id.strip().lower()] = v
            self._vendor_map[v.legal_name.strip().lower()] = v
            for alias in v.aliases:
                self._vendor_map[alias.strip().lower()] = v

    def get_vendor(self, identifier: str) -> VendorRecord | None:
        """Find vendor by vendor_id, legal name, or known alias."""
        if not identifier:
            return None
        return self._vendor_map.get(identifier.strip().lower())

    def list_vendors(self) -> list[VendorRecord]:
        """Return all vendor records in master."""
        return list(self._vendors)

    def evaluate_vendor_context(
        self,
        invoice: Invoice,
        vendor_record: VendorRecord | None = None,
        history_result: VendorHistoryResult | None = None,
    ) -> VendorContextResult:
        """Deterministically compare invoice with vendor profile and historical parameters."""
        vendor = vendor_record
        if vendor is None:
            if invoice.vendor_id and invoice.vendor_id.strip():
                vendor = self.get_vendor(invoice.vendor_id)
            elif invoice.vendor_name and invoice.vendor_name.strip():
                vendor = self.get_vendor(invoice.vendor_name)

        details: list[str] = []

        po_val = getattr(invoice, "purchase_order_number", None) or (invoice.metadata or {}).get("purchase_order_number") or (invoice.metadata or {}).get("po_number")
        po_provided = bool(po_val and str(po_val).strip())

        if vendor is None:
            # Vendor not explicitly defined in synthetic master
            hist_count = history_result.invoice_count if history_result else 0
            is_new = history_result.new_vendor if history_result is not None else True
            details.append("Vendor not found in corporate vendor master.")
            return VendorContextResult(
                vendor_id=invoice.vendor_id or "UNKNOWN",
                vendor_name=invoice.vendor_name,
                vendor_exists=False,
                is_active=True if not is_new else False,
                status="ACTIVE" if not is_new else "UNKNOWN",
                country="US",
                approved_currencies=[invoice.currency] if invoice.currency else ["USD"],
                currency_supported=True,
                payment_terms="Net 30",
                po_required=False,
                po_provided=po_provided,
                missing_po=False,
                onboarding_status="APPROVED" if not is_new else "UNREGISTERED",
                bank_verification_status="VERIFIED" if not is_new else "NOT_VERIFIED",
                is_new_vendor=is_new,
                historical_invoice_count=hist_count,
                historical_total_spend=Decimal("0.00"),
                historical_average=None,
                historical_largest=None,
                normal_range_min=None,
                normal_range_max=None,
                current_amount=invoice.total,
                deviation_factor=None,
                is_above_normal_range=False,
                details=details,
            )

        # Vendor exists in master
        hist_count = vendor.historical_invoice_count
        if history_result and history_result.invoice_count > 0:
            hist_count = max(hist_count, history_result.invoice_count)

        is_new = (hist_count == 0 or vendor.onboarding_status == "PENDING")

        curr_supported = (invoice.currency.upper() in [c.upper() for c in vendor.approved_currencies])
        if not curr_supported:
            details.append(f"Currency '{invoice.currency}' is not in approved list: {vendor.approved_currencies}")

        missing_po = vendor.po_required and not po_provided
        if missing_po:
            details.append("Purchase order is required by vendor agreement but was not provided.")

        # Deviation calculation
        deviation_factor: Decimal | None = None
        if vendor.historical_average_invoice > Decimal("0.00") and invoice.total is not None:
            deviation_factor = (invoice.total / vendor.historical_average_invoice).quantize(
                MONEY_QUANTUM, rounding=ROUNDING_STRATEGY
            )
            details.append(
                f"Historical average is {vendor.historical_average_invoice} {invoice.currency}. Deviation factor: {deviation_factor}x."
            )
        else:
            details.append("Insufficient history to calculate deviation factor.")

        # Range checks
        is_above_normal = False
        if vendor.normal_invoice_max > Decimal("0.00") and invoice.total is not None:
            if invoice.total > vendor.normal_invoice_max:
                is_above_normal = True
                details.append(
                    f"Invoice total ({invoice.total}) exceeds normal range maximum ({vendor.normal_invoice_max})."
                )

        if vendor.status != "ACTIVE":
            details.append(f"Vendor status is '{vendor.status}' (not ACTIVE).")

        if vendor.onboarding_status != "APPROVED":
            details.append(f"Vendor onboarding status is '{vendor.onboarding_status}' (not APPROVED).")

        return VendorContextResult(
            vendor_id=vendor.vendor_id,
            vendor_name=vendor.legal_name,
            vendor_exists=True,
            is_active=vendor.is_active,
            status=vendor.status,
            country=vendor.country,
            approved_currencies=vendor.approved_currencies,
            currency_supported=curr_supported,
            payment_terms=vendor.payment_terms,
            po_required=vendor.po_required,
            po_provided=po_provided,
            missing_po=missing_po,
            onboarding_status=vendor.onboarding_status,
            bank_verification_status=vendor.bank_verification_status,
            is_new_vendor=is_new,
            historical_invoice_count=hist_count,
            historical_total_spend=vendor.historical_total_spend,
            historical_average=vendor.historical_average_invoice if vendor.historical_average_invoice > 0 else None,
            historical_largest=vendor.historical_largest_invoice if vendor.historical_largest_invoice > 0 else None,
            normal_range_min=vendor.normal_invoice_min if vendor.normal_invoice_min > 0 else None,
            normal_range_max=vendor.normal_invoice_max if vendor.normal_invoice_max > 0 else None,
            current_amount=invoice.total,
            deviation_factor=deviation_factor,
            is_above_normal_range=is_above_normal,
            details=details,
        )


# Global singleton instance
vendor_context_service = VendorContextService()
