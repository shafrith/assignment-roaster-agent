"""Application exception hierarchy and FastAPI exception handlers.

Every handler responds with ``{"detail": <message>}`` to match the ``ErrorResponse`` contract.
"""

import logging

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

logger = logging.getLogger(__name__)

RATE_LIMIT_MESSAGE = "Konjam slow-a po machan, romba request anuppura! 🐢"


class AppError(Exception):
    """Base class for expected, user-facing application errors."""

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_detail: str = "Something went wrong."

    def __init__(self, detail: str | None = None, status_code: int | None = None) -> None:
        """Create an error.

        Args:
            detail: User-safe message returned in the response body.
            status_code: Optional override of the class-level HTTP status code.
        """
        self.detail = detail or self.default_detail
        if status_code is not None:
            self.status_code = status_code
        super().__init__(self.detail)


class BadRequestError(AppError):
    """The request is malformed or semantically invalid (400)."""

    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Bad request."


class NotFoundError(AppError):
    """The requested resource does not exist or is not visible to the caller (404)."""

    status_code = status.HTTP_404_NOT_FOUND
    default_detail = "Not found."


class ConflictError(AppError):
    """The request conflicts with the current resource state (409)."""

    status_code = status.HTTP_409_CONFLICT
    default_detail = "Conflict."


class RateLimitedError(AppError):
    """A quota or rate limit was exceeded (429)."""

    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    default_detail = RATE_LIMIT_MESSAGE


class UpstreamError(AppError):
    """An upstream service (GitHub, OpenAI) failed (502)."""

    status_code = status.HTTP_502_BAD_GATEWAY
    default_detail = "Upstream service failed."


async def app_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Convert an :class:`AppError` into a JSON ``{"detail": ...}`` response."""
    if not isinstance(exc, AppError):
        return await unhandled_error_handler(request, exc)
    if exc.status_code >= 500:
        logger.error(
            "%s on %s %s: %s", type(exc).__name__, request.method, request.url.path, exc.detail
        )
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


async def rate_limit_handler(request: Request, exc: Exception) -> JSONResponse:
    """Convert a slowapi :class:`RateLimitExceeded` into a 429 ``{"detail": ...}`` response."""
    logger.info("Rate limit exceeded on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS, content={"detail": RATE_LIMIT_MESSAGE}
    )


async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Log unexpected exceptions and return a generic 500 without leaking internals."""
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error."},
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Attach all application exception handlers to ``app``."""
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(RateLimitExceeded, rate_limit_handler)
    app.add_exception_handler(Exception, unhandled_error_handler)
