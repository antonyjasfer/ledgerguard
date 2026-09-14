"""Structured error definitions and exception handlers for LedgerGuard REST API.

Ensures no internal stack traces, credentials, secrets, or raw documents are leaked.
"""

import logging
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("ledgerguard.api.errors")


class LedgerGuardAPIException(Exception):
    """Base domain exception for LedgerGuard API."""

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    error_code: str = "INTERNAL_ERROR"
    message: str = "An internal processing error occurred."

    def __init__(self, message: str | None = None, details: dict[str, Any] | None = None):
        super().__init__(message or self.message)
        self.message = message or self.message
        self.details = details or {}


class InvalidInvoiceError(LedgerGuardAPIException):
    status_code = status.HTTP_400_BAD_REQUEST
    error_code = "INVALID_INVOICE"
    message = "Invalid invoice data provided."


class AuthenticationError(LedgerGuardAPIException):
    status_code = status.HTTP_401_UNAUTHORIZED
    error_code = "UNAUTHORIZED"
    message = "Invalid or missing API key."


class InvoiceNotFoundError(LedgerGuardAPIException):
    status_code = status.HTTP_404_NOT_FOUND
    error_code = "INVOICE_NOT_FOUND"
    message = "The requested invoice was not found."


class ConflictError(LedgerGuardAPIException):
    status_code = status.HTTP_409_CONFLICT
    error_code = "CONFLICT"
    message = "Operation conflict or invalid state transition."


class PayloadTooLargeError(LedgerGuardAPIException):
    status_code = status.HTTP_413_CONTENT_TOO_LARGE
    error_code = "PAYLOAD_TOO_LARGE"
    message = "Document size exceeds the maximum permitted threshold."


class DependencyUnavailableError(LedgerGuardAPIException):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    error_code = "DEPENDENCY_UNAVAILABLE"
    message = "Required storage or queuing dependency is unavailable."


def get_request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None) or request.headers.get("X-Request-ID")


def register_error_handlers(app: FastAPI) -> None:
    """Register structured error handlers on the FastAPI application."""

    @app.exception_handler(LedgerGuardAPIException)
    async def handle_ledgerguard_exception(request: Request, exc: LedgerGuardAPIException):
        req_id = get_request_id(request)
        logger.warning(
            "API error: status=%d, error=%s, message=%s, request_id=%s",
            exc.status_code,
            exc.error_code,
            exc.message,
            req_id,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": exc.error_code,
                "message": exc.message,
                "request_id": req_id,
                "details": exc.details,
            },
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError):
        req_id = get_request_id(request)
        # Format field errors safely without exposing raw payload bytes
        safe_errors = []
        for err in exc.errors():
            loc = ".".join(str(l) for l in err.get("loc", []))
            safe_errors.append({
                "field": loc,
                "issue": err.get("msg", "Invalid value"),
                "type": err.get("type", "value_error"),
            })
        logger.info("Validation error: count=%d, request_id=%s", len(safe_errors), req_id)
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content={
                "error": "VALIDATION_ERROR",
                "message": "Input validation failed for request payload.",
                "request_id": req_id,
                "details": {"validation_errors": safe_errors},
            },
        )

    @app.exception_handler(TypeError)
    async def handle_type_error(request: Request, exc: TypeError):
        req_id = get_request_id(request)
        logger.info("Validation type error: %s, request_id=%s", exc, req_id)
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content={
                "error": "VALIDATION_ERROR",
                "message": "Input validation failed for request payload.",
                "request_id": req_id,
                "details": {
                    "validation_errors": [
                        {
                            "field": "body",
                            "issue": str(exc),
                            "type": "type_error",
                        }
                    ]
                },
            },
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_starlette_http_exception(request: Request, exc: StarletteHTTPException):
        req_id = get_request_id(request)
        error_code = "HTTP_ERROR"
        if exc.status_code == status.HTTP_404_NOT_FOUND:
            error_code = "NOT_FOUND"
        elif exc.status_code == status.HTTP_401_UNAUTHORIZED:
            error_code = "UNAUTHORIZED"
        elif exc.status_code == status.HTTP_403_FORBIDDEN:
            error_code = "FORBIDDEN"
        elif exc.status_code == status.HTTP_405_METHOD_NOT_ALLOWED:
            error_code = "METHOD_NOT_ALLOWED"

        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": error_code,
                "message": str(exc.detail),
                "request_id": req_id,
                "details": {},
            },
            headers=dict(exc.headers or {}),
        )

    @app.exception_handler(Exception)
    async def handle_generic_exception(request: Request, exc: Exception):
        req_id = get_request_id(request)
        logger.exception("Unhandled server exception: request_id=%s, type=%s", req_id, type(exc).__name__)
        # NEVER leak stack traces, AWS request internals, or credentials in response
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected internal server error occurred.",
                "request_id": req_id,
                "details": {},
            },
        )
