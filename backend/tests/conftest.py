"""Shared pytest fixtures.

Environment variables are set BEFORE the app is imported. ``DATABASE_URL`` comes from the
environment (CI's Postgres service) and defaults to the local throwaway container::

    docker run -d --name roaster-test-db -p 5437:5432 -e POSTGRES_USER=roaster \
        -e POSTGRES_PASSWORD=roaster -e POSTGRES_DB=roaster_test postgres:16-alpine

Isolation is by truncating every table before and after each DB test: the pipeline opens its own
``SessionLocal`` sessions, so rollback-only isolation would not see (or undo) its writes.
"""

import os

os.environ["ENVIRONMENT"] = "test"
os.environ.setdefault("DATABASE_URL", "postgresql://roaster:roaster@localhost:5437/roaster_test")
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production")
os.environ.setdefault("FRONTEND_URL", "http://localhost:5173")
os.environ.setdefault("LOG_LEVEL", "WARNING")

import ssl  # noqa: E402
from collections.abc import Callable, Iterator  # noqa: E402
from decimal import Decimal  # noqa: E402
from itertools import count  # noqa: E402
from typing import Any  # noqa: E402

import httpx._transports.default as httpx_default  # noqa: E402
import pytest  # noqa: E402
import respx  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402
from starlette.requests import Request  # noqa: E402

from app import models  # noqa: E402,F401
from app.config import settings  # noqa: E402
from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models.repo_analysis import RepoAnalysis  # noqa: E402
from app.models.roast import Roast  # noqa: E402
from app.models.submission import Submission, SubmissionStatus  # noqa: E402
from app.rate_limit import client_quota_key, limiter  # noqa: E402
from app.services import roast_engine  # noqa: E402
from tests.support import FakeOpenAI  # noqa: E402

_TABLES = ", ".join(table.name for table in reversed(Base.metadata.sorted_tables))
_ids = count(1)


@pytest.fixture(scope="session", autouse=True)
def _reuse_default_ssl_context() -> Iterator[None]:
    """Build httpx's default SSL context once per session.

    Loading the certifi bundle takes seconds on some machines and every ``httpx.AsyncClient``
    does it. Tests never open real TLS connections (respx intercepts everything).
    """
    original = httpx_default.create_ssl_context
    cache: dict[tuple[object, ...], ssl.SSLContext] = {}

    def cached(verify: Any = True, cert: Any = None, trust_env: bool = True) -> ssl.SSLContext:
        if verify is not True or cert is not None:
            return original(verify=verify, cert=cert, trust_env=trust_env)
        key = (trust_env,)
        if key not in cache:
            cache[key] = original(verify=verify, cert=cert, trust_env=trust_env)
        return cache[key]

    httpx_default.create_ssl_context = cached
    try:
        yield
    finally:
        httpx_default.create_ssl_context = original


@pytest.fixture(scope="session")
def _schema() -> Iterator[None]:
    """Create the schema once (no-op when CI already ran ``alembic upgrade head``)."""
    Base.metadata.create_all(bind=engine)
    yield
    engine.dispose()


def _truncate() -> None:
    with engine.begin() as conn:
        conn.execute(text("SET LOCAL lock_timeout = '10s'"))
        conn.execute(text(f"TRUNCATE {_TABLES} RESTART IDENTITY CASCADE"))


@pytest.fixture
def db(_schema: None) -> Iterator[Session]:
    """A DB session on a freshly truncated database."""
    _truncate()
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()
        _truncate()


@pytest.fixture
def client(db: Session) -> Iterator[TestClient]:
    """TestClient with the app lifespan running."""
    with TestClient(app) as test_client:
        yield test_client


def quota_key_for(host: str) -> str:
    """The daily-quota key the app derives for a client at ``host``."""
    return client_quota_key(Request({"type": "http", "headers": [], "client": (host, 50000)}))


# TestClient requests come from the "testclient" host.
TEST_CLIENT_KEY = quota_key_for("testclient")


@pytest.fixture
def github_mock() -> Iterator[respx.MockRouter]:
    """respx router; any unmocked outbound HTTP request fails the test."""
    with respx.mock(assert_all_called=False) as router:
        yield router


@pytest.fixture
def fake_llm(monkeypatch: pytest.MonkeyPatch) -> FakeOpenAI:
    """Patch the roast engine's client factory with a fake OpenAI (never the real API)."""
    fake = FakeOpenAI()
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "test-openai-key")
    monkeypatch.setattr(roast_engine, "client_factory", lambda: fake)
    return fake


@pytest.fixture
def rate_limiting() -> Iterator[None]:
    """Temporarily enable the slowapi limiter (disabled when ENVIRONMENT=test)."""
    limiter.reset()
    limiter.enabled = True
    try:
        yield
    finally:
        limiter.enabled = False
        limiter.reset()


@pytest.fixture
def completed_submission_factory(db: Session) -> Callable[..., Submission]:
    """Insert a completed submission with analysis and roast rows (no pipeline)."""

    def make(**overrides: Any) -> Submission:
        n = next(_ids)
        fields: dict[str, Any] = {
            "repo_url": f"https://github.com/someone/repo{n}",
            "repo_owner": "someone",
            "repo_name": f"repo{n}",
            "default_branch": "main",
            "commit_sha": f"{n:040x}",
            "status": SubmissionStatus.completed,
            "is_public": True,
            "share_slug": f"slug{n}",
        }
        fields.update(overrides)
        submission = Submission(**fields)
        db.add(submission)
        db.flush()
        db.add(
            RepoAnalysis(
                submission_id=submission.id,
                languages={"Python": 100},
                file_count=3,
                has_readme=True,
                commit_count=4,
                findings=[],
                largest_files=[],
                sampled_files=[],
            )
        )
        db.add(
            Roast(
                submission_id=submission.id,
                score=Decimal("6.5"),
                verdict_title="Notebook Nayagan",
                roast_text="Dei machan!",
                strengths=["Has a README"],
                issues=[
                    {"category": "testing", "severity": "high", "file": None, "message": "No tests"}
                ],
                fix_tips=["a", "b", "c"],
                model="gpt-test-model",
                input_tokens=10,
                output_tokens=5,
            )
        )
        db.commit()
        db.refresh(submission)
        return submission

    return make
