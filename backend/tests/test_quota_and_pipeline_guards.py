"""Quota attempts and retry rules (SEC-2, COR-3), stale sweeping (COR-2), pipeline concurrency
and timeouts (PERF-2), and client quota keys (SEC-4)."""

import asyncio
import threading
import weakref
from datetime import UTC, datetime, timedelta
from typing import Any

import anthropic
import httpx
import pytest
import respx
from fastapi.testclient import TestClient
from sqlalchemy import text, update
from sqlalchemy.orm import Session
from starlette.requests import Request

from app.config import settings
from app.database import SessionLocal
from app.exceptions import RateLimitedError
from app.models.repo_analysis import RepoAnalysis
from app.models.roast_attempt import RoastAttempt
from app.models.submission import Submission, SubmissionStatus
from app.rate_limit import client_ip, client_quota_key
from app.services import pipeline, submission_service
from app.services.pipeline import STALE_FAILURE_MESSAGE, fail_stale_submissions, run_pipeline
from tests.conftest import TEST_CLIENT_KEY, quota_key_for
from tests.support import FakeAnthropic, FixtureRepo, mock_github_repos
from tests.test_roasts import URL, add_pending, by_slug, create


def _always_fail_claude(fake_claude: FakeAnthropic) -> None:
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    fake_claude.set_outputs(anthropic.APITimeoutError(request=request))


def _status(db: Session, submission_id: int) -> SubmissionStatus:
    db.expire_all()
    row = db.get(Submission, submission_id)
    assert row is not None
    return row.status


# ---------------------------------------------------------------------------- SEC-2 quota


def test_five_retries_exhaust_daily_quota(
    client: TestClient,
    db: Session,
    github_mock: respx.MockRouter,
    fake_claude: FakeAnthropic,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Every retry is a quota attempt, so a failing repo can't burn unlimited Claude calls."""
    monkeypatch.setattr(settings, "ROAST_DAILY_LIMIT", 5)
    monkeypatch.setattr(settings, "ROAST_MAX_RETRIES", 100)
    repo = FixtureRepo("clean_repo")
    mock_github_repos(github_mock, repo)
    _always_fail_claude(fake_claude)

    slug = create(client, repo.url).json()["shareSlug"]  # attempt 1
    retry = f"{URL}/{slug}/retry"
    statuses = [client.post(retry).status_code for _ in range(5)]
    assert statuses == [202, 202, 202, 202, 429]  # attempts 2-5, then the quota is gone
    assert db.query(RoastAttempt).count() == 5
    calls = fake_claude.call_count
    assert create(client, repo.url).status_code == 429  # new submissions too
    assert fake_claude.call_count == calls


def test_retry_cap_per_submission(
    client: TestClient,
    github_mock: respx.MockRouter,
    fake_claude: FakeAnthropic,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "ROAST_DAILY_LIMIT", 100)
    monkeypatch.setattr(settings, "ROAST_MAX_RETRIES", 2)
    repo = FixtureRepo("clean_repo")
    mock_github_repos(github_mock, repo)
    _always_fail_claude(fake_claude)

    slug = create(client, repo.url).json()["shareSlug"]
    retry = f"{URL}/{slug}/retry"
    assert client.post(retry).status_code == 202
    assert client.post(retry).status_code == 202
    capped = client.post(retry)
    assert capped.status_code == 409
    assert capped.json() == {"detail": submission_service.RETRY_LIMIT_MESSAGE}
    # A fresh submission of the same repo is still allowed (and charged).
    assert create(client, repo.url).status_code == 202


@pytest.mark.parametrize("failure", ["private", "too_large"])
def test_retry_refused_for_deterministic_failure(
    client: TestClient,
    db: Session,
    github_mock: respx.MockRouter,
    fake_claude: FakeAnthropic,
    failure: str,
) -> None:
    if failure == "private":
        repo = FixtureRepo("clean_repo", private=True)
    else:
        repo = FixtureRepo("clean_repo", size_kb=settings.max_repo_size_kb + 1)
    mock_github_repos(github_mock, repo)
    slug = create(client, repo.url).json()["shareSlug"]
    assert client.get(f"{URL}/{slug}").json()["status"] == "failed"

    response = client.post(f"{URL}/{slug}/retry")
    assert response.status_code == 409
    assert response.json() == {"detail": submission_service.RETRY_NOT_RETRYABLE_MESSAGE}
    assert db.query(RoastAttempt).count() == 1  # the refused retry cost nothing
    assert fake_claude.call_count == 0


def test_transient_failure_is_retryable(
    client: TestClient,
    db: Session,
    github_mock: respx.MockRouter,
) -> None:
    github_mock.route(host="api.github.com").respond(503)
    slug = create(client, "https://github.com/a/b").json()["shareSlug"]
    row = by_slug(db, slug)
    assert row.status == SubmissionStatus.failed and row.error_retryable


def test_old_attempts_do_not_count(
    client: TestClient,
    db: Session,
    github_mock: respx.MockRouter,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "ROAST_DAILY_LIMIT", 1)
    old = datetime.now(UTC) - timedelta(hours=25)
    db.add(RoastAttempt(client_key=TEST_CLIENT_KEY, created_at=old))
    db.commit()
    github_mock.route(host="api.github.com").respond(404)
    assert create(client, "https://github.com/a/b").status_code == 202
    assert submission_service.attempts_used_today(db, TEST_CLIENT_KEY) == 1


def test_quota_check_is_serialized_per_client(db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    """COR-3: a concurrent request waits for the client lock, then sees the other's attempt."""
    monkeypatch.setattr(settings, "ROAST_DAILY_LIMIT", 1)
    holder = SessionLocal()
    holder.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"), {"key": TEST_CLIENT_KEY}
    )
    holder.add(RoastAttempt(client_key=TEST_CLIENT_KEY))
    holder.flush()

    outcome: dict[str, str] = {}

    def contender() -> None:
        with SessionLocal() as session:
            try:
                submission_service.create_submission(
                    session, TEST_CLIENT_KEY, "https://github.com/a/b"
                )
                outcome["result"] = "created"
            except RateLimitedError:
                outcome["result"] = "limited"

    thread = threading.Thread(target=contender)
    try:
        thread.start()
        thread.join(timeout=0.5)
        assert thread.is_alive()  # blocked on the client's advisory lock
    finally:
        holder.commit()
        holder.close()
        thread.join(timeout=10)
    assert outcome["result"] == "limited"
    assert db.query(Submission).count() == 0


# ---------------------------------------------------------------------------- COR-2 sweeping


def test_startup_fails_all_orphaned_submissions(db: Session) -> None:
    from app import main

    fresh = {
        status: add_pending(db, status=status, share_slug=f"orphan-{status}")
        for status in (
            SubmissionStatus.pending,
            SubmissionStatus.analyzing,
            SubmissionStatus.roasting,
            SubmissionStatus.completed,
        )
    }
    with TestClient(main.app):
        pass
    db.expire_all()
    for status, sub in fresh.items():
        row = db.get(Submission, sub.id)
        assert row is not None
        if status == SubmissionStatus.completed:
            assert row.status == SubmissionStatus.completed
        else:
            assert row.status == SubmissionStatus.failed
            assert row.error_message == STALE_FAILURE_MESSAGE
            assert row.error_retryable


def test_periodic_sweep_skips_in_flight(db: Session) -> None:
    old = datetime.now(UTC) - timedelta(minutes=pipeline.STALE_SUBMISSION_MINUTES + 1)
    queued = add_pending(db, share_slug="queued")
    orphan = add_pending(db, share_slug="orphan")
    db.execute(update(Submission).values(updated_at=old))
    db.commit()
    pipeline._in_flight.add(queued.id)
    try:
        assert fail_stale_submissions() == 1
    finally:
        pipeline._in_flight.discard(queued.id)
    assert _status(db, queued.id) == SubmissionStatus.pending
    assert _status(db, orphan.id) == SubmissionStatus.failed


async def test_sweeper_loop_runs_and_survives_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[int] = []

    def flaky() -> int:
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("db blip")
        return 3

    monkeypatch.setattr(pipeline, "fail_stale_submissions", flaky)
    task = asyncio.create_task(pipeline.sweep_stale_submissions_forever(interval_seconds=0.01))
    for _ in range(300):
        if len(calls) >= 3:
            break
        await asyncio.sleep(0.01)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert len(calls) >= 3


# ---------------------------------------------------------------------------- pipeline guards


async def test_pipeline_semaphore_limits_concurrency(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "MAX_CONCURRENT_ROASTS", 2)
    monkeypatch.setattr(pipeline, "_semaphores", weakref.WeakKeyDictionary())
    running = 0
    peak = 0

    async def fake_guarded(_submission_id: int) -> None:
        nonlocal running, peak
        running += 1
        peak = max(peak, running)
        await asyncio.sleep(0.02)
        running -= 1

    monkeypatch.setattr(pipeline, "_run_guarded", fake_guarded)
    await asyncio.gather(*(run_pipeline(i) for i in range(6)))
    assert peak == 2
    assert not pipeline._in_flight


async def test_pipeline_timeout_marks_failed(db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    sub = add_pending(db)

    async def hang(*_args: object) -> None:
        await asyncio.sleep(5)

    monkeypatch.setattr(pipeline, "PIPELINE_TIMEOUT_SECONDS", 0.05)
    monkeypatch.setattr(pipeline, "_run", hang)
    await run_pipeline(sub.id)
    db.expire_all()
    row = db.get(Submission, sub.id)
    assert row is not None and row.status == SubmissionStatus.failed
    assert row.error_message == pipeline.TIMEOUT_FAILURE_MESSAGE and row.error_retryable


def test_swept_submission_is_not_completed_by_late_pipeline(
    client: TestClient,
    db: Session,
    github_mock: respx.MockRouter,
    fake_claude: FakeAnthropic,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """COR-3: a pipeline whose row was failed meanwhile must not overwrite it."""
    repo = FixtureRepo("clean_repo")
    mock_github_repos(github_mock, repo)
    original = pipeline.analyze_repo

    async def analyze_then_get_swept(*args: Any) -> Any:
        result = await original(*args)
        pipeline._in_flight.clear()
        assert fail_stale_submissions(max_age=None) == 1
        return result

    monkeypatch.setattr(pipeline, "analyze_repo", analyze_then_get_swept)
    slug = create(client, repo.url).json()["shareSlug"]
    done = client.get(f"{URL}/{slug}").json()
    assert done["status"] == "failed"
    assert done["errorMessage"] == STALE_FAILURE_MESSAGE
    assert fake_claude.call_count == 0
    assert db.query(RepoAnalysis).count() == 0


def test_dedupe_ignores_roasts_from_older_prompt_versions(
    client: TestClient,
    db: Session,
    github_mock: respx.MockRouter,
    fake_claude: FakeAnthropic,
) -> None:
    """COR-7: a prompt change invalidates previously generated roasts for dedupe."""
    repo = FixtureRepo("clean_repo")
    mock_github_repos(github_mock, repo)
    first_slug = create(client, repo.url).json()["shareSlug"]
    first = by_slug(db, first_slug)
    assert first.roast is not None
    assert first.roast.prompt_version == pipeline.PROMPT_VERSION

    first.roast.prompt_version = "1999-01-01.0"
    db.commit()
    second_slug = create(client, repo.url).json()["shareSlug"]
    assert fake_claude.call_count == 2  # not deduped against the old-prompt roast
    assert by_slug(db, second_slug).deduped_from_submission_id is None


def test_complete_refuses_terminal_submission(db: Session) -> None:
    sub = add_pending(db, status=SubmissionStatus.failed)
    with SessionLocal() as session, pytest.raises(pipeline._Superseded):
        pipeline._complete(session, sub.id)
    assert _status(db, sub.id) == SubmissionStatus.failed


def test_mark_failed_never_overwrites_completed(db: Session) -> None:
    sub = add_pending(db, status=SubmissionStatus.completed)
    pipeline._mark_failed(sub.id, "late failure")
    db.expire_all()
    row = db.get(Submission, sub.id)
    assert row is not None and row.status == SubmissionStatus.completed
    assert row.error_message is None


# ---------------------------------------------------------------------------- SEC-4 limiter keys


@pytest.mark.usefixtures("rate_limiting")
def test_rate_limit_is_per_ip(client: TestClient) -> None:
    statuses = [create(client, "bad-url").status_code for _ in range(11)]
    assert statuses[10] == 429


def _request(headers: dict[str, str], peer: tuple[str, int] | None) -> Request:
    raw = [(k.lower().encode(), v.encode()) for k, v in headers.items()]
    return Request({"type": "http", "headers": raw, "client": peer})


def test_client_ip_ignores_forwarded_headers() -> None:
    peer = ("203.0.113.9", 1234)
    assert client_ip(_request({}, peer)) == "ip:203.0.113.9"
    # X-Forwarded-For is never trusted here (only uvicorn's --proxy-headers may rewrite it).
    assert client_ip(_request({"X-Forwarded-For": "1.2.3.4"}, peer)) == "ip:203.0.113.9"
    assert client_ip(_request({}, None)) == "ip:unknown"


def test_client_quota_key_is_stable_and_opaque() -> None:
    key = client_quota_key(_request({}, ("203.0.113.9", 1234)))
    assert key == quota_key_for("203.0.113.9")  # the port does not matter
    assert len(key) == 64 and "203.0.113.9" not in key
    assert key != quota_key_for("203.0.113.10")
