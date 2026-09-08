"""Observability and request correlation middleware for LedgerGuard API.

Generates and propagates unique request_id tokens across HTTP requests, responses,
and execution logs. Strictly redacts sensitive credentials, secrets, and raw payloads.
"""

import logging
import time
import uuid

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

logger = logging.getLogger("ledgerguard.api.access")


class RequestCorrelationMiddleware(BaseHTTPMiddleware):
    """Middleware to extract or assign request_id and inject into request state and response headers."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Extract existing X-Request-ID or generate new unique correlation token
        req_id = request.headers.get("X-Request-ID")
        if not req_id or not req_id.strip():
            req_id = f"req_{uuid.uuid4().hex[:12]}"

        # Bind to request state
        request.state.request_id = req_id

        start_time = time.perf_counter()

        # Log incoming request safely (never log headers that contain credentials)
        logger.info(
            "HTTP request started. method=%s, path=%s, request_id=%s, client=%s",
            request.method,
            request.url.path,
            req_id,
            request.client.host if request.client else "unknown",
        )

        try:
            response = await call_next(request)
            duration_ms = (time.perf_counter() - start_time) * 1000.0

            # Attach correlation ID to response headers
            response.headers["X-Request-ID"] = req_id

            logger.info(
                "HTTP request completed. method=%s, path=%s, status=%d, duration_ms=%.2f, request_id=%s",
                request.method,
                request.url.path,
                response.status_code,
                duration_ms,
                req_id,
            )
            return response
        except Exception as exc:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            logger.exception(
                "HTTP request failed with unhandled exception. method=%s, path=%s, duration_ms=%.2f, request_id=%s, error_type=%s",
                request.method,
                request.url.path,
                duration_ms,
                req_id,
                type(exc).__name__,
            )
            return JSONResponse(
                status_code=500,
                content={
                    "error": "INTERNAL_SERVER_ERROR",
                    "message": "An unexpected internal server error occurred.",
                    "request_id": req_id,
                    "details": {},
                },
                headers={"X-Request-ID": req_id},
            )
