"""Health check, OpenAPI, and global error handling."""

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from starlette.requests import Request

from app.config import Settings
from app.exceptions import AppError, NotFoundError, app_error_handler
from app.main import app
from app.services import submission_service


def test_health(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_openapi_documents_every_endpoint(client: TestClient) -> None:
    paths = client.get("/openapi.json").json()["paths"]
    for path in (
        "/api/v1/roasts",
        "/api/v1/roasts/{share_slug}",
        "/api/v1/roasts/{share_slug}/retry",
        "/api/v1/public/roasts/{share_slug}",
    ):
        assert path in paths
    assert not any(path.startswith(("/api/v1/auth", "/api/v1/submissions")) for path in paths)


def test_cors_allows_frontend_origin(client: TestClient) -> None:
    response = client.options(
        "/health",
        headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"},
    )
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_unhandled_errors_return_generic_500(db: object, monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*_args: object) -> None:
        raise RuntimeError("database password is hunter2")

    monkeypatch.setattr(submission_service, "get_roast_by_slug", boom)
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/api/v1/roasts/some-slug")
    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error."}
    assert "hunter2" not in response.text


async def test_app_error_handler_paths() -> None:
    request = Request({"type": "http", "method": "GET", "path": "/x", "headers": []})
    response = await app_error_handler(request, AppError("upstream broke"))
    assert response.status_code == 500
    response = await app_error_handler(request, NotFoundError(status_code=410))
    assert response.status_code == 410
    response = await app_error_handler(request, ValueError("not an AppError"))
    assert response.status_code == 500


STRONG_KEY = "q8Zr2vN0xL5tW9yB3cH7mK1pD4fG6jS0aE2uR8iO"


def test_settings_normalization() -> None:
    settings = Settings(
        DATABASE_URL="postgres://u:p@h/db",
        SECRET_KEY=STRONG_KEY,
        FRONTEND_URL="https://example.com/",
        ENVIRONMENT="production",
    )
    assert settings.DATABASE_URL == "postgresql+psycopg://u:p@h/db"
    assert settings.FRONTEND_URL == "https://example.com"
    assert settings.is_production
    assert settings.max_repo_size_kb == settings.MAX_REPO_SIZE_MB * 1024
    assert not hasattr(settings, "GITHUB_CLIENT_ID")  # no login, so no OAuth settings
    settings.warn_missing_secrets()
    assert Settings(DATABASE_URL="postgresql://x", SECRET_KEY="k").DATABASE_URL == (
        "postgresql+psycopg://x"
    )
    assert Settings(DATABASE_URL="sqlite://", SECRET_KEY="k").DATABASE_URL == "sqlite://"


@pytest.mark.parametrize(
    "secret_key",
    [
        "your-secret-key-change-in-production",  # .env.example
        "test-secret-key-not-for-production",  # tests
        "short-but-random-Zx81",
        "x" * 31,
        "CHANGE_ME_" + "a" * 40,
    ],
)
def test_production_refuses_weak_secret_key(secret_key: str) -> None:
    with pytest.raises(ValidationError, match="SECRET_KEY"):
        Settings(
            DATABASE_URL="postgresql://x",
            SECRET_KEY=secret_key,
            FRONTEND_URL="https://example.com",
            ENVIRONMENT="production",
        )


def test_production_requires_https_frontend() -> None:
    with pytest.raises(ValidationError, match="https"):
        Settings(
            DATABASE_URL="postgresql://x",
            SECRET_KEY=STRONG_KEY,
            FRONTEND_URL="http://example.com",
            ENVIRONMENT="production",
        )


@pytest.mark.parametrize("url", ["http://localhost:8080", "http://127.0.0.1:5173"])
def test_production_allows_http_loopback_frontend(url: str) -> None:
    settings = Settings(
        DATABASE_URL="postgresql://x",
        SECRET_KEY=STRONG_KEY,
        FRONTEND_URL=url,
        ENVIRONMENT="production",
    )
    assert settings.is_production


def test_weak_secret_key_allowed_outside_production() -> None:
    for environment in ("development", "test"):
        settings = Settings(
            DATABASE_URL="postgresql://x",
            SECRET_KEY="your-secret-key-change-in-production",
            ENVIRONMENT=environment,
        )
        assert not settings.is_production
