"""Dependency injection and authentication boundary providers for LedgerGuard API.

Supports pluggable service instances (S3, DynamoDB, SQS) to facilitate offline
deterministic testing without AWS calls.
"""

import logging
import secrets
from typing import Annotated

from fastapi import Depends, Header, Request

from app.api.errors import AuthenticationError
from app.config import Settings, get_settings
from app.services.dynamodb import DynamoDBInvoiceRepository
from app.services.interfaces import DocumentStore, InvoiceRepository, JobQueue
from app.services.s3 import S3DocumentStore
from app.services.sqs import SQSJobQueue

logger = logging.getLogger("ledgerguard.api.auth")


def get_current_settings() -> Settings:
    """Return application configuration settings."""
    return get_settings()


def get_document_store(
    settings: Annotated[Settings, Depends(get_current_settings)]
) -> DocumentStore:
    """Provide document store implementation (Amazon S3)."""
    return S3DocumentStore(settings=settings)


def get_invoice_repository(
    settings: Annotated[Settings, Depends(get_current_settings)]
) -> InvoiceRepository:
    """Provide invoice repository implementation (Amazon DynamoDB)."""
    return DynamoDBInvoiceRepository(settings=settings)


def get_job_queue(
    settings: Annotated[Settings, Depends(get_current_settings)]
) -> JobQueue:
    """Provide background job queue implementation (Amazon SQS)."""
    return SQSJobQueue(settings=settings)


def require_api_key(
    request: Request,
    settings: Annotated[Settings, Depends(get_current_settings)],
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> str | None:
    """Validate API key for protected LedgerGuard endpoints.

    Checks X-API-Key header or Authorization: Bearer <key>.
    Never logs or echoes back credential values.
    """
    configured_key = (
        settings.LEDGERGUARD_API_KEY.get_secret_value()
        if settings.LEDGERGUARD_API_KEY
        else None
    )

    # If an API key is configured in settings, enforcement is strictly required
    if configured_key:
        provided_key: str | None = None
        if x_api_key:
            provided_key = x_api_key.strip()
        elif authorization:
            parts = authorization.strip().split()
            if len(parts) == 2 and parts[0].lower() == "bearer":
                provided_key = parts[1]
            elif len(parts) == 1:
                provided_key = parts[0]

        if not provided_key:
            req_id = getattr(request.state, "request_id", "unknown")
            logger.warning("Rejected request missing API key. request_id=%s, path=%s", req_id, request.url.path)
            raise AuthenticationError("Missing API key. Provide via X-API-Key or Authorization header.")

        # Constant-time comparison to protect against timing attacks
        if not secrets.compare_digest(provided_key, configured_key):
            req_id = getattr(request.state, "request_id", "unknown")
            logger.warning("Rejected request with invalid API key. request_id=%s, path=%s", req_id, request.url.path)
            raise AuthenticationError("Invalid API key.")

        return provided_key

    # If no key is configured in the environment, allow access (local development default)
    return None
