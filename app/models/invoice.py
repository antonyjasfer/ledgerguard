"""Invoice and LineItem domain data models for LedgerGuard.

Strictly enforces Decimal for all monetary and quantitative amounts.
Zero floating-point numbers permitted.
"""

from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from pydantic import BaseModel, Field, field_validator

# Centralized financial precision rules
MONEY_QUANTUM = Decimal("0.01")
ROUNDING_STRATEGY = ROUND_HALF_UP


def quantize_money(amount: Decimal | None) -> Decimal | None:
    """Quantize monetary amount to 2 decimal places using ROUND_HALF_UP."""
    if amount is None:
        return None
    return amount.quantize(MONEY_QUANTUM, rounding=ROUNDING_STRATEGY)


def _reject_float(val: Any, field_name: str) -> Any:
    """Ensure floating-point types are rejected to avoid precision loss."""
    if isinstance(val, float):
        raise TypeError(
            f"Floating-point values are strictly forbidden for financial calculations in '{field_name}'. "
            f"Use Decimal or a string representation instead."
        )
    return val


class LineItem(BaseModel):
    """Line item in an Accounts Payable invoice."""

    description: str = Field(..., min_length=1, description="Description of the goods or services")
    quantity: Decimal = Field(default=Decimal("1"), ge=Decimal("0"), description="Quantity purchased")
    unit_price: Decimal = Field(..., ge=Decimal("0"), description="Unit price per item")
    tax_rate: Decimal = Field(default=Decimal("0.00"), ge=Decimal("0"), description="Tax rate applied as percentage (e.g. 5.0 for 5%)")
    discount: Decimal = Field(default=Decimal("0.00"), ge=Decimal("0"), description="Line-level discount amount")

    @field_validator("quantity", "unit_price", "tax_rate", "discount", mode="before")
    @classmethod
    def check_no_float(cls, v: Any, info: Any) -> Any:
        return _reject_float(v, info.field_name)

    def calculate_line_subtotal(self) -> Decimal:
        """Calculate line subtotal as quantity * unit_price quantized to 2 decimal places."""
        raw = self.quantity * self.unit_price
        return raw.quantize(MONEY_QUANTUM, rounding=ROUNDING_STRATEGY)

    def calculate_line_tax(self) -> Decimal:
        """Calculate tax on the discounted subtotal."""
        discounted = self.calculate_line_subtotal() - self.discount
        raw = discounted * (self.tax_rate / Decimal("100"))
        return raw.quantize(MONEY_QUANTUM, rounding=ROUNDING_STRATEGY)

    def calculate_line_total(self) -> Decimal:
        """Calculate total amount for this line item."""
        return self.calculate_line_subtotal() - self.discount + self.calculate_line_tax()


class Invoice(BaseModel):
    """Normalized internal canonical invoice model for LedgerGuard AP pipeline."""

    invoice_id: str = Field(..., min_length=1, description="Unique invoice transaction identifier")
    invoice_number: str = Field(..., min_length=1, description="Vendor-supplied invoice reference number")
    vendor_id: str = Field(..., min_length=1, description="Vendor identifier")
    vendor_name: str = Field(..., min_length=1, description="Legal name of vendor")
    customer_name: str = Field(..., min_length=1, description="Customer or organization billed")
    invoice_date: date = Field(..., description="Invoice issue date")
    due_date: date | None = Field(default=None, description="Payment due date")
    currency: str = Field(default="USD", min_length=3, max_length=3, description="ISO-4217 currency code")

    subtotal: Decimal | None = Field(default=None, ge=Decimal("0"), description="Invoice-level subtotal")
    tax: Decimal | None = Field(default=None, ge=Decimal("0"), description="Invoice-level tax amount")
    discount: Decimal | None = Field(default=None, ge=Decimal("0"), description="Invoice-level discount amount")
    shipping: Decimal | None = Field(default=Decimal("0"), ge=Decimal("0"), description="Invoice-level shipping amount")
    total: Decimal | None = Field(default=None, ge=Decimal("0"), description="Invoice-level grand total")

    purchase_order_number: str | None = Field(default=None, description="Optional Purchase Order reference")
    line_items: list[LineItem] = Field(default_factory=list, description="List of invoiced line items")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Arbitrary invoice metadata")

    @field_validator("subtotal", "tax", "discount", "shipping", "total", mode="before")
    @classmethod
    def check_no_float_financials(cls, v: Any, info: Any) -> Any:
        return _reject_float(v, info.field_name)
