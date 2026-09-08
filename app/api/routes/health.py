"""Liveness and readiness endpoints for LedgerGuard API."""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import get_current_settings
from app.api.schemas import HealthResponse, ReadyResponse
from app.config import Settings

router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Liveness health check",
    description="Returns 200 OK if the API process is alive. Fast and unauthenticated.",
)
async def health_check() -> HealthResponse:
    return HealthResponse(
        status="healthy",
        service="ledgerguard",
        version="0.1.0",
    )


@router.get(
    "/ready",
    response_model=ReadyResponse,
    summary="Readiness dependency check",
    description="Validates that configuration and resource settings are safely defined.",
)
async def readiness_check(
    settings: Annotated[Settings, Depends(get_current_settings)]
) -> ReadyResponse:
    storage_mode = settings.LEDGERGUARD_STORAGE_MODE
    model_provider = settings.LEDGERGUARD_MODEL_PROVIDER

    dependencies = {
        "storage_mode": storage_mode,
        "model_provider": model_provider,
        "dynamodb_table_configured": bool(settings.LEDGERGUARD_DYNAMODB_TABLE),
        "s3_bucket_configured": bool(settings.LEDGERGUARD_S3_BUCKET),
        "sqs_queue_configured": bool(settings.LEDGERGUARD_SQS_QUEUE_URL),
        "aws_region": settings.AWS_REGION,
    }

    all_configured = (
        bool(settings.LEDGERGUARD_DYNAMODB_TABLE)
        and (storage_mode == "local" or bool(settings.LEDGERGUARD_S3_BUCKET))
        and (storage_mode == "local" or bool(settings.LEDGERGUARD_SQS_QUEUE_URL))
    )

    status_str = "ready" if all_configured else "misconfigured"

    return ReadyResponse(
        status=status_str,
        service="ledgerguard",
        dependencies=dependencies,
    )
