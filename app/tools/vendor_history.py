"""Deterministic vendor history analysis tool for LedgerGuard.

Aggregates historical invoice volume, spend by currency, date horizons,
and recent transaction density.
Crucially enforces multi-currency safety: never sums amounts across different currencies.
Zero LLM reliance, zero external database calls.
"""

from collections import defaultdict
from datetime import date
from decimal import Decimal
from typing import Sequence

from app.models.invoice import Invoice, MONEY_QUANTUM, ROUNDING_STRATEGY
from app.models.verification import VendorHistoryResult


def get_vendor_history(
    vendor_id: str,
    history: Sequence[Invoice],
    recent_days: int = 30,
    reference_date: date | None = None,
) -> VendorHistoryResult:
    """Compile vendor historical metrics from a sequence of prior invoices.

    Args:
        vendor_id: Vendor identifier to filter.
        history: Sequence of historical invoices.
        recent_days: Number of days to consider an invoice recent.
        reference_date: Anchor date for recency calculation (defaults to latest invoice date or today).

    Returns:
        VendorHistoryResult containing currency-segregated spend, volume, and date spans.
    """
    norm_vendor = vendor_id.strip().lower()
    matching = [inv for inv in history if inv.vendor_id.strip().lower() == norm_vendor]

    if not matching:
        return VendorHistoryResult(
            vendor_id=vendor_id,
            invoice_count=0,
            total_spend={},
            average_invoice_amount={},
            largest_invoice_amount={},
            first_invoice_date=None,
            last_invoice_date=None,
            currency_distribution={},
            recent_invoice_count=0,
            new_vendor=True,
        )

    # Segregate amounts by currency to guarantee currency safety
    currency_totals: dict[str, list[Decimal]] = defaultdict(list)
    all_dates: list[date] = []

    for inv in matching:
        all_dates.append(inv.invoice_date)
        if inv.total is not None:
            currency_totals[inv.currency].append(inv.total)

    first_date = min(all_dates)
    last_date = max(all_dates)

    # Recency evaluation relative to reference_date or last historical invoice date
    anchor_date = reference_date or last_date
    recent_count = sum(
        1 for d in all_dates if 0 <= (anchor_date - d).days <= recent_days
    )

    total_spend: dict[str, Decimal] = {}
    avg_spend: dict[str, Decimal] = {}
    max_spend: dict[str, Decimal] = {}

    for curr, totals in currency_totals.items():
        if totals:
            curr_sum = sum(totals).quantize(MONEY_QUANTUM, rounding=ROUNDING_STRATEGY)
            curr_avg = (curr_sum / Decimal(len(totals))).quantize(
                MONEY_QUANTUM, rounding=ROUNDING_STRATEGY
            )
            curr_max = max(totals).quantize(MONEY_QUANTUM, rounding=ROUNDING_STRATEGY)
            total_spend[curr] = curr_sum
            avg_spend[curr] = curr_avg
            max_spend[curr] = curr_max

    return VendorHistoryResult(
        vendor_id=vendor_id,
        invoice_count=len(matching),
        total_spend=total_spend,
        average_invoice_amount=avg_spend,
        largest_invoice_amount=max_spend,
        first_invoice_date=first_date,
        last_invoice_date=last_date,
        currency_distribution=total_spend.copy(),
        recent_invoice_count=recent_count,
        new_vendor=False,
    )
