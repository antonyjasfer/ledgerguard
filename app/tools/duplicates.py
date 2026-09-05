"""Deterministic duplicate invoice detection tool for LedgerGuard.

Identifies confirmed duplicates (same vendor + invoice number) and
possible duplicates (same vendor + total amount within a date proximity threshold).
Zero LLM reliance, fully deterministic evidence-based rules.
"""

from datetime import date
from typing import Sequence

from app.models.invoice import Invoice
from app.models.verification import DuplicateCheckResult, DuplicateStatus


def check_duplicate_invoice(
    invoice: Invoice,
    history: Sequence[Invoice],
    max_days: int = 7,
) -> DuplicateCheckResult:
    """Evaluate candidate invoice against historical invoices for duplication.

    Rules:
    - CONFIRMED_DUPLICATE: Identical vendor_id AND invoice_number.
    - POSSIBLE_DUPLICATE: Identical vendor_id AND identical total AND
      absolute date difference <= max_days.
    - NO_DUPLICATE: No matching historical records.

    Self-comparison (matching invoice_id) is explicitly skipped.
    """
    confirmed_ids: list[str] = []
    possible_ids: list[str] = []

    norm_vendor = invoice.vendor_id.strip().lower()
    norm_number = invoice.invoice_number.strip().lower()

    for past_inv in history:
        # Ignore exact self identity
        if past_inv.invoice_id == invoice.invoice_id:
            continue

        past_vendor = past_inv.vendor_id.strip().lower()
        past_number = past_inv.invoice_number.strip().lower()

        # Rule 1: Confirmed duplicate (same vendor + same invoice number)
        if past_vendor == norm_vendor and past_number == norm_number:
            confirmed_ids.append(past_inv.invoice_id)
            continue

        # Rule 2: Possible duplicate (same vendor + same total + within max_days)
        if (
            past_vendor == norm_vendor
            and invoice.total is not None
            and past_inv.total is not None
            and past_inv.total == invoice.total
            and past_inv.currency == invoice.currency
        ):
            date_diff = abs((invoice.invoice_date - past_inv.invoice_date).days)
            if date_diff <= max_days:
                possible_ids.append(past_inv.invoice_id)

    if confirmed_ids:
        return DuplicateCheckResult(
            status=DuplicateStatus.CONFIRMED_DUPLICATE,
            matched_invoice_ids=confirmed_ids,
            match_reasons=["same_vendor", "same_invoice_number"],
            details=[
                f"Confirmed duplicate match with {len(confirmed_ids)} invoice(s): "
                f"{', '.join(confirmed_ids)}"
            ],
        )

    if possible_ids:
        return DuplicateCheckResult(
            status=DuplicateStatus.POSSIBLE_DUPLICATE,
            matched_invoice_ids=possible_ids,
            match_reasons=["same_vendor", "same_amount", f"invoice_date_within_{max_days}_days"],
            details=[
                f"Possible duplicate match with {len(possible_ids)} invoice(s) within {max_days} days: "
                f"{', '.join(possible_ids)}"
            ],
        )

    return DuplicateCheckResult(
        status=DuplicateStatus.NO_DUPLICATE,
        matched_invoice_ids=[],
        match_reasons=[],
        details=["No duplicate patterns found in historical invoice dataset."],
    )
