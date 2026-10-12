"""FastAPI application entry point for the Assignment Roaster API."""

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.middleware import SlowAPIMiddleware

from app.config import settings
from app.exceptions import register_exception_handlers
from app.rate_limit import limiter
from app.routers import auth, public, submissions
from app.services.pipeline import fail_stale_submissions, sweep_stale_submissions_forever

API_PREFIX = "/api/v1"


def configure_logging(level: str) -> None:
    """Configure root logging once for the process.

    Args:
        level: Log level name such as ``"INFO"`` or ``"DEBUG"``.
    """
    logging.basicConfig(
        level=level.upper(),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )


configure_logging(settings.LOG_LEVEL)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Startup: warn about missing secrets, fail orphaned submissions, start the sweeper.

    Pipelines run as in-process background tasks, so none survive a restart: every
    non-terminal submission is failed (retryable) at startup. A periodic task then fails
    submissions orphaned later (for example by a lost background task). Shutdown cancels it.
    """
    settings.warn_missing_secrets()
    try:
        failed = fail_stale_submissions(max_age=None)
        if failed:
            logger.info("Marked %d orphaned submissions as failed", failed)
    except Exception:
        logger.exception("Failed to mark stale submissions as failed")
    sweeper = asyncio.create_task(sweep_stale_submissions_forever())
    logger.info("Assignment Roaster API started (environment=%s)", settings.ENVIRONMENT)
    try:
        yield
    finally:
        sweeper.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await sweeper


def create_app() -> FastAPI:
    """Build and configure the FastAPI application.

    Returns:
        The configured application instance.
    """
    application = FastAPI(
        title="Assignment Roaster API",
        version="1.0.0",
        lifespan=lifespan,
    )

    application.state.limiter = limiter
    application.add_middleware(SlowAPIMiddleware)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.FRONTEND_URL],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(application)

    application.include_router(auth.router, prefix=API_PREFIX)
    application.include_router(submissions.router, prefix=API_PREFIX)
    application.include_router(public.router, prefix=API_PREFIX)

    @application.get("/health", tags=["health"])
    async def health() -> dict[str, str]:
        """Liveness probe."""
        return {"status": "ok"}

    return application


app = create_app()
