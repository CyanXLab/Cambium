"""
Cambium Global Exception Handling.

Provides:
  - Custom exception classes with HTTP status codes
  - FastAPI global exception handlers
  - Consistent error response format
  - Structured error logging

This replaces the 364 bare `except Exception: pass` patterns with a
centralized error handling strategy.
"""
from __future__ import annotations

import traceback
from typing import Any, Dict, Optional
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.logging_config import get_logger

log = get_logger(__name__)


# ============================================================
# Custom exception hierarchy
# ============================================================

class CambiumError(Exception):
    """Base exception for all Cambium errors.
    Each subclass defines a default status_code and error_code.
    """
    status_code: int = 500
    error_code: str = "internal_error"

    def __init__(self, message: str, *, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class NotFoundError(CambiumError):
    status_code = 404
    error_code = "not_found"


class ValidationError(CambiumError):
    status_code = 422
    error_code = "validation_error"


class AuthenticationError(CambiumError):
    status_code = 401
    error_code = "authentication_required"


class AuthorizationError(CambiumError):
    status_code = 403
    error_code = "forbidden"


class ConflictError(CambiumError):
    status_code = 409
    error_code = "conflict"


class RateLimitError(CambiumError):
    status_code = 429
    error_code = "rate_limited"


class LLMError(CambiumError):
    status_code = 502
    error_code = "llm_error"


class DatabaseError(CambiumError):
    status_code = 500
    error_code = "database_error"


class ToolExecutionError(CambiumError):
    status_code = 500
    error_code = "tool_execution_error"


# ============================================================
# Error response format
# ============================================================

def error_response(
    status_code: int,
    error_code: str,
    message: str,
    details: Optional[Dict] = None,
    request_id: Optional[str] = None,
) -> JSONResponse:
    """Build a consistent error JSON response."""
    body: Dict[str, Any] = {
        "error": {
            "code": error_code,
            "message": message,
        }
    }
    if details:
        body["error"]["details"] = details
    if request_id:
        body["error"]["request_id"] = request_id
    return JSONResponse(status_code=status_code, content=body)


# ============================================================
# FastAPI exception handlers
# ============================================================

async def cambium_error_handler(request: Request, exc: CambiumError) -> JSONResponse:
    """Handle known CambiumError subclasses."""
    log.warning(
        "request.error",
        extra={
            "error_code": exc.error_code,
            "status": exc.status_code,
            "path": str(request.url.path),
            "method": request.method,
            "error_message": exc.message,
        },
    )
    return error_response(exc.status_code, exc.error_code, exc.message, exc.details)


async def generic_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle any uncaught exception. Logs full traceback, returns 500."""
    log.error(
        "request.unhandled_error",
        extra={
            "error_type": type(exc).__name__,
            "path": str(request.url.path),
            "method": request.method,
            "traceback": traceback.format_exc(),
        },
    )
    return error_response(
        500, "internal_error",
        f"An unexpected error occurred: {type(exc).__name__}",
    )


async def http_exception_handler(request: Request, exc) -> JSONResponse:
    """Handle FastAPI HTTPException."""
    from app.logging_config import get_logger
    log = get_logger(__name__)
    log.warning(
        "request.http_error",
        extra={
            "status": exc.status_code,
            "path": str(request.url.path),
            "detail": str(exc.detail),
        },
    )
    return error_response(exc.status_code, "http_error", str(exc.detail))


async def validation_exception_handler(request: Request, exc) -> JSONResponse:
    """Handle Pydantic RequestValidationError."""
    errors = []
    for e in exc.errors():
        errors.append({
            "loc": e.get("loc", []),
            "msg": e.get("msg", ""),
            "type": e.get("type", ""),
        })
    log.warning(
        "request.validation_error",
        extra={"path": str(request.url.path), "errors": errors},
    )
    return error_response(422, "validation_error", "Request validation failed", {"errors": errors})


# ============================================================
# Request logging middleware
# ============================================================

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log every HTTP request with method, path, status, and duration."""

    async def dispatch(self, request: Request, call_next):
        import time
        start = time.time()

        # Skip health checks to reduce noise
        path = str(request.url.path)
        if path in ("/api/health", "/"):
            return await call_next(request)

        try:
            response = await call_next(request)
            duration_ms = (time.time() - start) * 1000
            log.info(
                "request.completed",
                extra={
                    "method": request.method,
                    "path": path,
                    "status": response.status_code,
                    "duration_ms": round(duration_ms, 2),
                },
            )
            return response
        except Exception as exc:
            duration_ms = (time.time() - start) * 1000
            log.error(
                "request.failed",
                extra={
                    "method": request.method,
                    "path": path,
                    "error": str(exc),
                    "duration_ms": round(duration_ms, 2),
                },
            )
            raise


# ============================================================
# Register all handlers with a FastAPI app
# ============================================================

def register_exception_handlers(app):
    """Register all exception handlers on a FastAPI app instance."""
    from fastapi.exceptions import RequestValidationError, HTTPException

    app.add_exception_handler(CambiumError, cambium_error_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, generic_error_handler)
    app.add_middleware(RequestLoggingMiddleware)
    log.info("exception_handlers.registered")
