"""Vendor domain models and configuration for LedgerGuard."""

from pydantic import BaseModel, Field


class VendorRecord(BaseModel):
    """Vendor reference record."""

    vendor_id: str = Field(..., min_length=1, description="Unique vendor ID")
    name: str = Field(..., min_length=1, description="Official registered business name")
    tax_id: str | None = Field(default=None, description="Tax identifier / EIN / VAT number")
    is_active: bool = Field(default=True, description="Whether vendor is authorized for active AP processing")
