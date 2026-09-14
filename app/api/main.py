"""FastAPI application entrypoint for LedgerGuard.

Configures application middleware, structured error handling, OpenAPI documentation,
and mounts health, invoice verification, dashboard, enterprise context, and bulk batch ingestion routes.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.errors import register_error_handlers
from app.api.middleware import RequestCorrelationMiddleware
from app.api.routes import batches, dashboard, enterprise, health, invoices
from app.config import get_settings

logger = logging.getLogger("ledgerguard.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for application startup and shutdown events."""
    settings = get_settings()
    logger.info(
        "LedgerGuard API starting up. provider=%s, storage_mode=%s, region=%s",
        settings.LEDGERGUARD_MODEL_PROVIDER,
        settings.LEDGERGUARD_STORAGE_MODE,
        settings.AWS_REGION,
    )
    yield
    logger.info("LedgerGuard API shutting down.")


def create_app() -> FastAPI:
    """Application factory creating and configuring the FastAPI instance."""
    app = FastAPI(
        title="LedgerGuard Invoice Verification API",
        description=(
            "Autonomous Accounts Payable invoice verification backend powered by "
            "deterministic verification tools, enterprise company policy, vendor master, "
            "bulk batch ingestion, Strands Agent reasoning, Decision Guard, and Amazon Bedrock Mantle / AWS infrastructure."
        ),
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # 1. Register Observability & Correlation Middleware
    app.add_middleware(RequestCorrelationMiddleware)

    # 1b. Register CORS Middleware for Web Frontend
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:4173", "http://127.0.0.1:4173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 2. Register Structured Domain & Validation Error Handlers
    register_error_handlers(app)

    # 3. Mount Route Endpoints
    app.include_router(health.router)
    app.include_router(dashboard.router)
    app.include_router(enterprise.router)
    app.include_router(invoices.router)
    app.include_router(batches.router)

    return app


# Root application instance for ASGI servers (e.g. uvicorn app.api.main:app)
app = create_app()
