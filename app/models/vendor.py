"""Vendor domain models and configuration for LedgerGuard."""

from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


def _reject_float(val: Any, field_name: str) -> Any:
    if isinstance(val, float):
        raise TypeError(f"Floating-point values are forbidden in '{field_name}'. Use Decimal.")
    return val


class VendorRecord(BaseModel):
    """Vendor reference record and enterprise profile."""

    vendor_id: str = Field(..., min_length=1, description="Unique vendor identifier")
    legal_name: str = Field(..., min_length=1, description="Official registered business name")
    status: str = Field(default="ACTIVE", description="Vendor status: ACTIVE, PENDING, SUSPENDED, INACTIVE")
    country: str = Field(default="US", description="ISO country code of vendor registration")
    approved_currencies: list[str] = Field(
        default_factory=lambda: ["USD"],
        description="Currencies authorized for billing by this vendor",
    )
    payment_terms: str = Field(default="Net 30", description="Commercial payment terms (e.g. Net 30)")
    po_required: bool = Field(default=False, description="Whether purchase orders are strictly required")
    onboarding_status: str = Field(
        default="APPROVED",
        description="Onboarding verification status: APPROVED, PENDING, REJECTED",
    )
    bank_verification_status: str = Field(
        default="VERIFIED",
        description="Bank details verification status: VERIFIED or NOT_VERIFIED (no real bank accounts)",
    )
    created_at: str = Field(default="2024-01-01T00:00:00Z", description="Vendor creation timestamp")
    historical_invoice_count: int = Field(default=0, ge=0, description="Count of historical invoices processed")
    historical_total_spend: Decimal = Field(
        default=Decimal("0.00"),
        ge=Decimal("0.00"),
        description="Cumulative spend across historical invoices",
    )
    historical_average_invoice: Decimal = Field(
        default=Decimal("0.00"),
        ge=Decimal("0.00"),
        description="Average spend per historical invoice",
    )
    historical_largest_invoice: Decimal = Field(
        default=Decimal("0.00"),
        ge=Decimal("0.00"),
        description="Maximum historical invoice total",
    )
    normal_invoice_min: Decimal = Field(
        default=Decimal("0.00"),
        ge=Decimal("0.00"),
        description="Baseline minimum typical invoice amount",
    )
    normal_invoice_max: Decimal = Field(
        default=Decimal("0.00"),
        ge=Decimal("0.00"),
        description="Baseline maximum typical invoice amount",
    )
    aliases: list[str] = Field(default_factory=list, description="Common name aliases or search keys")
    tax_id: str | None = Field(default=None, description="Tax identifier / EIN / VAT number")
    is_active: bool = Field(default=True, description="Whether vendor is authorized for active AP processing")

    @model_validator(mode="before")
    @classmethod
    def sync_name_and_status(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "name" in data and "legal_name" not in data:
                data["legal_name"] = data["name"]
            if "status" in data and "is_active" not in data:
                data["is_active"] = (str(data["status"]).upper() == "ACTIVE")
            elif "is_active" in data and "status" not in data:
                data["status"] = "ACTIVE" if data["is_active"] else "INACTIVE"
        return data

    @field_validator(
        "historical_total_spend",
        "historical_average_invoice",
        "historical_largest_invoice",
        "normal_invoice_min",
        "normal_invoice_max",
        mode="before",
    )
    @classmethod
    def check_no_float(cls, v: Any, info: Any) -> Any:
        return _reject_float(v, info.field_name)

    @property
    def name(self) -> str:
        return self.legal_name
