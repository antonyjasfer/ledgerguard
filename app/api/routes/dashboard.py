"""Dashboard statistics and overview route."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.api.dependencies import get_invoice_repository, require_api_key
from app.api.schemas import DashboardStatsResponse
from app.services.interfaces import InvoiceRepository

logger = logging.getLogger("ledgerguard.api.dashboard")

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get(
    "/stats",
    response_model=DashboardStatsResponse,
    summary="Get dashboard statistics",
    description="Retrieve aggregate invoice counts, decision metrics, risk distributions, and monetary totals.",
)
async def get_dashboard_stats(
    request: Request,
    repository: Annotated[InvoiceRepository, Depends(get_invoice_repository)],
    _api_key: Annotated[str | None, Depends(require_api_key)],
    batch_id: str | None = None,
    date_range: str | None = None,
) -> DashboardStatsResponse:
    req_id = getattr(request.state, "request_id", "unknown")
    logger.info("Dashboard stats requested. request_id=%s, batch_id=%s, date_range=%s", req_id, batch_id, date_range)
    try:
        raw_stats = repository.get_dashboard_stats(batch_id=batch_id, date_range=date_range)
    except TypeError:
        raw_stats = repository.get_dashboard_stats()
    return DashboardStatsResponse(**raw_stats)
