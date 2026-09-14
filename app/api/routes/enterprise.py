"""Enterprise context, company policy, and vendor master routes."""

from decimal import Decimal
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.api.dependencies import require_api_key
from app.api.schemas import PolicyConfigResponse, VendorListResponse, VendorRecordResponse
from app.models.policy import ApprovalRoutingTier, PolicyConfig
from app.services.vendor_context import vendor_context_service

logger = logging.getLogger("ledgerguard.api.enterprise")

router = APIRouter(prefix="", tags=["Enterprise Context"])


@router.get(
    "/policy",
    response_model=PolicyConfigResponse,
    summary="Get active corporate policy",
    description="Retrieve the configured Accounts Payable policy rules and approval matrix.",
)
async def get_active_policy(
    request: Request,
    _api_key: Annotated[str | None, Depends(require_api_key)] = None,
) -> PolicyConfigResponse:
    req_id = getattr(request.state, "request_id", "unknown")
    logger.info("Active policy requested. request_id=%s", req_id)

    policy = PolicyConfig.get_demo_enterprise_policy()

    matrix_tiers = [
        {
            "tier": ApprovalRoutingTier.AUTO_APPROVAL_ALLOWED.value,
            "condition": f"0.00 to {policy.auto_approval_limit} USD",
            "action": "Automated verification eligible for straight-through processing",
        },
        {
            "tier": ApprovalRoutingTier.MANAGER_REVIEW.value,
            "condition": f"{policy.auto_approval_limit + Decimal('0.01')} to {policy.high_value_threshold} USD",
            "action": "Routing to AP Department Manager for authorization",
        },
        {
            "tier": ApprovalRoutingTier.FINANCE_DIRECTOR_REVIEW.value,
            "condition": f"Above {policy.high_value_threshold} USD",
            "action": "Escalation to Finance Director for executive review",
        },
        {
            "tier": ApprovalRoutingTier.MANUAL_REVIEW.value,
            "condition": "New Vendor / Missing PO / Unsupported Currency / Large Discount",
            "action": "Routing to AP Specialist for document and compliance check",
        },
        {
            "tier": ApprovalRoutingTier.BLOCK.value,
            "condition": "Confirmed Duplicate / Arithmetic Mismatch / Critical Risk",
            "action": "Immediate disbursement block and audit flag",
        },
    ]

    return PolicyConfigResponse(
        company_name=policy.company_name,
        company_id=policy.company_id,
        supported_currencies=policy.supported_currencies,
        default_currency=policy.default_currency,
        auto_approval_limit=policy.auto_approval_limit,
        high_value_threshold=policy.high_value_threshold,
        new_vendor_requires_review=policy.new_vendor_requires_review,
        duplicate_requires_block=policy.duplicate_requires_block,
        possible_duplicate_requires_review=policy.possible_duplicate_requires_review,
        possible_duplicate_days=policy.possible_duplicate_days,
        recent_invoice_days=policy.recent_invoice_days,
        missing_po_requires_review=policy.missing_po_requires_review,
        tax_mismatch_requires_review=policy.tax_mismatch_requires_review,
        arithmetic_mismatch_requires_block=policy.arithmetic_mismatch_requires_block,
        unsupported_currency_requires_review=policy.unsupported_currency_requires_review,
        maximum_discount_percent=policy.maximum_discount_percent,
        large_discount_requires_review=policy.large_discount_requires_review,
        required_fields=policy.required_fields,
        approval_matrix_tiers=matrix_tiers,
    )


@router.get(
    "/vendors",
    response_model=VendorListResponse,
    summary="List vendor master records",
    description="Retrieve all registered vendor profiles from the enterprise vendor master.",
)
async def list_vendors(
    request: Request,
    _api_key: Annotated[str | None, Depends(require_api_key)] = None,
) -> VendorListResponse:
    req_id = getattr(request.state, "request_id", "unknown")
    logger.info("Vendor list requested. request_id=%s", req_id)

    vendors = vendor_context_service.list_vendors()
    items = [
        VendorRecordResponse(
            vendor_id=v.vendor_id,
            legal_name=v.legal_name,
            status=v.status,
            country=v.country,
            approved_currencies=v.approved_currencies,
            payment_terms=v.payment_terms,
            po_required=v.po_required,
            onboarding_status=v.onboarding_status,
            bank_verification_status=v.bank_verification_status,
            created_at=v.created_at,
            historical_invoice_count=v.historical_invoice_count,
            historical_total_spend=v.historical_total_spend,
            historical_average_invoice=v.historical_average_invoice,
            historical_largest_invoice=v.historical_largest_invoice,
            normal_invoice_min=v.normal_invoice_min,
            normal_invoice_max=v.normal_invoice_max,
            aliases=v.aliases,
        )
        for v in vendors
    ]
    return VendorListResponse(items=items, total=len(items))


@router.get(
    "/vendors/{vendor_id}",
    response_model=VendorRecordResponse,
    summary="Get vendor master record",
    description="Retrieve a single vendor master profile by vendor identifier.",
)
async def get_vendor(
    vendor_id: str,
    request: Request,
    _api_key: Annotated[str | None, Depends(require_api_key)] = None,
) -> VendorRecordResponse:
    req_id = getattr(request.state, "request_id", "unknown")
    logger.info("Vendor details requested. vendor_id=%s, request_id=%s", vendor_id, req_id)

    v = vendor_context_service.get_vendor(vendor_id)
    if not v:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Vendor '{vendor_id}' not found in vendor master.",
        )

    return VendorRecordResponse(
        vendor_id=v.vendor_id,
        legal_name=v.legal_name,
        status=v.status,
        country=v.country,
        approved_currencies=v.approved_currencies,
        payment_terms=v.payment_terms,
        po_required=v.po_required,
        onboarding_status=v.onboarding_status,
        bank_verification_status=v.bank_verification_status,
        created_at=v.created_at,
        historical_invoice_count=v.historical_invoice_count,
        historical_total_spend=v.historical_total_spend,
        historical_average_invoice=v.historical_average_invoice,
        historical_largest_invoice=v.historical_largest_invoice,
        normal_invoice_min=v.normal_invoice_min,
        normal_invoice_max=v.normal_invoice_max,
        aliases=v.aliases,
    )
