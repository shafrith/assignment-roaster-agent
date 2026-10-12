"""Roast endpoints (no login) and the background pipeline (GitHub fixture repos + fake Claude)."""

import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import anthropic
import httpx
import pytest
import respx
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.models.repo_analysis import RepoAnalysis
from app.models.roast import Roast
from app.models.roast_attempt import RoastAttempt
from app.models.submission import Submission, SubmissionStatus
from app.services import pipeline, submission_service
from app.services.contracts import (
    GitHubUnavailableError,
    RepoNotFoundError,
    RoastGenerationError,
)
from app.services.github_url import INVALID_URL_MESSAGE
from app.services.pipeline import (
    GENERIC_FAILURE_MESSAGE,
    STALE_FAILURE_MESSAGE,
    fail_stale_submissions,
    run_pipeline,
)
from tests.conftest import TEST_CLIENT_KEY
from tests.support import (
    FIXTURE_SECRETS,
    FakeAnthropic,
    FixtureRepo,
    mock_github_repos,
    roast_input,
    tool_response,
)

URL = "/api/v1/roasts"
REPO_URL = "https://github.com/eval-fixtures/clean_repo"


def create(client: TestClient, repo_url: str = REPO_URL) -> httpx.Response:
    return client.post(URL, json={"repoUrl": repo_url})


def by_slug(db: Session, slug: str) -> Submission:
    """Load the submission behind a share slug (fresh from the DB)."""
    db.expire_all()
    submission = db.scalar(select(Submission).where(Submission.share_slug == slug))
    assert submission is not None
    return submission


def add_pending(db: Session, **overrides: Any) -> Submission:
    fields: dict[str, Any] = {
        "repo_url": REPO_URL,
        "repo_owner": "eval-fixtures",
        "repo_name": "clean_repo",
        "status": SubmissionStatus.pending,
        "share_slug": f"pending-{datetime.now(UTC).timestamp()}",
    }
    fields.update(overrides)
    submission = Submission(**fields)
    db.add(submission)
    db.commit()
    db.refresh(submission)
    return submission


# ---------------------------------------------------------------------------- create + pipeline


def test_create_runs_pipeline_end_to_end(
    client: TestClient,
    db: Session,
    github_mock: respx.MockRouter,
    fake_claude: FakeAnthropic,
) -> None:
    repo = FixtureRepo("clean_repo")
    mock_github_repos(github_mock, repo)

    response = create(client, repo.url + ".git")
    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "pending"
    assert body["repoUrl"] == REPO_URL
    assert body["repoOwner"] == "eval-fixtures"
    assert body["repoName"] == "clean_repo"
    assert body["analysis"] is None and body["roast"] is None
    assert "id" not in body and "author" not in body
    slug = body["shareSlug"]
    assert len(slug) >= 8

    # TestClient runs background tasks before returning, so the pipeline is done.
    detail = client.get(f"{URL}/{slug}")
    assert detail.status_code == 200
    done = detail.json()
    assert done["status"] == "completed"
    assert done["errorMessage"] is None
    assert done["completedAt"] is not None
    assert done["roast"]["score"] == 7.5
    assert isinstance(done["roast"]["score"], float)
    assert done["roast"]["verdictTitle"] == "Production Ready Ponnusamy"
    assert done["roast"]["fixTips"] == [
        "Add more tests.",
        "Pin dependencies.",
        "Add a CI workflow.",
    ]
    assert done["roast"]["issues"][0]["category"] == "testing"
    analysis = done["analysis"]
    assert analysis["hasReadme"] is True
    assert analysis["hasTests"] is True
    assert analysis["commitCount"] == 24
    assert analysis["languages"] == {"Python": 3120}
    assert "secretsFoundCount" not in analysis and "hasEnvFileCommitted" not in analysis
    assert "has_readme" not in detail.text  # camelCase on the wire

    assert fake_claude.call_count == 1
    prompt = fake_claude.messages.calls[0]["messages"][0]["content"]
    assert "app/llm.py" in prompt

    sub = by_slug(db, slug)
    assert sub.is_public is True
    assert sub.commit_sha == repo.head_sha
    assert sub.default_branch == "main"
    assert sub.roast is not None and sub.roast.input_tokens == 1000
    assert sub.analysis is not None and "README.md" in sub.analysis.sampled_files
    attempt = db.query(RoastAttempt).one()
    assert attempt.client_key == TEST_CLIENT_KEY
    assert "testclient" not in attempt.client_key  # the raw client address is never stored

    # A completed roast is also served by the public share endpoint.
    assert client.get(f"/api/v1/public/roasts/{slug}").status_code == 200


def test_messy_repo_secrets_never_stored_or_sent(
    client: TestClient,
    db: Session,
    github_mock: respx.MockRouter,
    fake_claude: FakeAnthropic,
) -> None:
    repo = FixtureRepo("messy_repo")
    mock_github_repos(github_mock, repo)
    fake_claude.set_outputs(tool_response(roast_input(score=8.0)))

    slug = create(client, repo.url).json()["shareSlug"]
    done = client.get(f"{URL}/{slug}").json()
    assert done["status"] == "completed"
    assert done["roast"]["score"] == 4.0  # committed-secret cap
    critical = [i for i in done["roast"]["issues"] if i["severity"] == "critical"]
    assert ".env" in {i["file"] for i in critical}

    sub = by_slug(db, slug)
    analysis_row = sub.analysis
    assert analysis_row is not None
    assert analysis_row.has_env_file_committed is True
    assert analysis_row.secrets_found_count > 0
    prompt = fake_claude.messages.calls[0]["messages"][0]["content"]
    stored = json.dumps(
        {c.key: getattr(analysis_row, c.key) for c in RepoAnalysis.__table__.columns},
        default=str,
    )
    for secret in FIXTURE_SECRETS:
        assert secret not in prompt
        assert secret not in stored
        assert secret not in json.dumps(done)
    assert "[REDACTED_SECRET]" in prompt


@pytest.mark.parametrize(
    "repo_url",
    [
        "https://gitlab.com/a/b",
        "https://github.com/settings/x",
        "not a url",
        "https://evil.com/a/b",
    ],
)
def test_create_invalid_url(client: TestClient, db: Session, repo_url: str) -> None:
    response = create(client, repo_url)
    assert response.status_code == 400
    assert response.json() == {"detail": INVALID_URL_MESSAGE}
    assert db.query(Submission).count() == 0


@pytest.mark.parametrize("body", [{}, {"repoUrl": ""}, {"repoUrl": "x" * 501}])
def test_create_validation(client: TestClient, body: dict) -> None:
    assert client.post(URL, json=body).status_code == 422


@pytest.mark.parametrize("private_style", ["flag", "404"])
def test_private_repo_fails_with_tanglish_message(
    client: TestClient,
    github_mock: respx.MockRouter,
    fake_claude: FakeAnthropic,
    private_style: str,
) -> None:
    if private_style == "flag":
        mock_github_repos(github_mock, FixtureRepo("clean_repo", owner="someone", private=True))
    else:
        mock_github_repos(github_mock)
    slug = create(client, "https://github.com/someone/clean_repo").json()["shareSlug"]
    done = client.get(f"{URL}/{slug}").json()
    assert done["status"] == "failed"
    assert done["errorMessage"] == RepoNotFoundError.default_detail
    assert done["errorRetryable"] is False
    assert fake_claude.call_count == 0


def test_repo_too_large_fails(
    client: TestClient,
    github_mock: respx.MockRouter,
    fake_claude: FakeAnthropic,
) -> None:
    repo = FixtureRepo("clean_repo", size_kb=settings.max_repo_size_kb + 1)
    mock_github_repos(github_mock, repo)
    slug = create(client, repo.url).json()["shareSlug"]
    done = client.get(f"{URL}/{slug}").json()
    assert done["status"] == "failed"
    assert "MB" in done["errorMessage"]


def test_github_outage_fails(
    client: TestClient,
    github_mock: respx.MockRouter,
    fake_claude: FakeAnthropic,
) -> None:
    github_mock.route(host="api.github.com").respond(503)
    slug = create(client, "https://github.com/a/b").json()["shareSlug"]
    done = client.get(f"{URL}/{slug}").json()
    assert done["status"] == "failed"
    assert done["errorMessage"] == GitHubUnavailableError.default_detail
    assert done["errorRetryable"] is True


def test_in_progress_roast_hides_partial_results(client: TestClient, db: Session) -> None:
    add_pending(db, status=SubmissionStatus.roasting, share_slug="in-progress")
    body = client.get(f"{URL}/in-progress").json()
    assert body["status"] == "roasting"
    assert body["analysis"] is None
    assert body["roast"] is None


def test_claude_failure_then_retry_succeeds(
    client: TestClient,
    db: Session,
    github_mock: respx.MockRouter,
    fake_claude: FakeAnthropic,
) -> None:
    mock_github_repos(github_mock, FixtureRepo("clean_repo"))
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    fake_claude.set_outputs(anthropic.APITimeoutError(request=request), tool_response())

    slug = create(client).json()["shareSlug"]
    failed = client.get(f"{URL}/{slug}").json()
    assert failed["status"] == "failed"
    assert failed["errorMessage"] == RoastGenerationError.default_detail
    assert failed["roast"] is None

    retried = client.post(f"{URL}/{slug}/retry")
    assert retried.status_code == 202
    assert retried.json()["status"] == "pending"
    assert retried.json()["errorMessage"] is None

    done = client.get(f"{URL}/{slug}").json()
    assert done["status"] == "completed"
    assert done["roast"]["score"] == 7.5
    assert fake_claude.call_count == 2
    assert db.query(RepoAnalysis).count() == 1


def test_unexpected_pipeline_error_uses_generic_message(
    client: TestClient,
    github_mock: respx.MockRouter,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_github_repos(github_mock, FixtureRepo("clean_repo"))

    async def explode(*_args: object) -> None:
        raise RuntimeError("internal detail that must not leak")

    monkeypatch.setattr(pipeline, "analyze_repo", explode)
    slug = create(client).json()["shareSlug"]
    done = client.get(f"{URL}/{slug}").json()
    assert done["status"] == "failed"
    assert done["errorMessage"] == GENERIC_FAILURE_MESSAGE


def test_dedupe_reuses_existing_roast(
    client: TestClient,
    db: Session,
    github_mock: respx.MockRouter,
    fake_claude: FakeAnthropic,
) -> None:
    repo = FixtureRepo("clean_repo")
    mock_github_repos(github_mock, repo)

    first_slug = create(client, repo.url).json()["shareSlug"]
    contents_after_first = len(repo.content_requests)
    second_slug = create(client, "https://github.com/EVAL-FIXTURES/Clean_Repo").json()["shareSlug"]

    assert fake_claude.call_count == 1  # second submission reused the roast
    assert len(repo.content_requests) == contents_after_first  # and the analysis
    a = client.get(f"{URL}/{first_slug}").json()
    b = client.get(f"{URL}/{second_slug}").json()
    assert b["status"] == "completed"
    assert b["roast"]["score"] == a["roast"]["score"]
    assert b["roast"]["verdictTitle"] == a["roast"]["verdictTitle"]
    assert b["analysis"] == a["analysis"]
    assert b["shareSlug"] != a["shareSlug"]
    assert db.query(Roast).count() == 2
    copy = by_slug(db, second_slug)
    assert copy.deduped_from_submission_id == by_slug(db, first_slug).id
    assert copy.roast is not None
    assert (copy.roast.input_tokens, copy.roast.output_tokens) == (0, 0)  # no Claude spend


def test_new_commit_is_not_deduped(
    client: TestClient,
    github_mock: respx.MockRouter,
    fake_claude: FakeAnthropic,
) -> None:
    repo = FixtureRepo("clean_repo")
    mock_github_repos(github_mock, repo)
    create(client, repo.url)
    repo.head_sha = "f" * 40
    create(client, repo.url)
    assert fake_claude.call_count == 2


# ---------------------------------------------------------------------------- run_pipeline direct


async def test_run_pipeline_missing_or_not_pending(db: Session) -> None:
    await run_pipeline(987_654)  # missing submission: no error
    sub = add_pending(db, status=SubmissionStatus.completed)
    await run_pipeline(sub.id)
    db.refresh(sub)
    assert sub.status == SubmissionStatus.completed


def test_mark_failed_never_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    def broken_session() -> None:
        raise RuntimeError("db down")

    monkeypatch.setattr(pipeline, "SessionLocal", broken_session)
    pipeline._mark_failed(1, "x")


def test_mark_failed_missing_submission(db: Session) -> None:
    pipeline._mark_failed(123_456, "x")


# ---------------------------------------------------------------------------- quota


def test_daily_quota_per_client(
    client: TestClient,
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
    github_mock: respx.MockRouter,
    fake_claude: FakeAnthropic,
) -> None:
    mock_github_repos(github_mock, FixtureRepo("clean_repo"))
    monkeypatch.setattr(settings, "ROAST_DAILY_LIMIT", 2)
    assert create(client).status_code == 202
    assert create(client).status_code == 202
    blocked = create(client)
    assert blocked.status_code == 429
    assert blocked.json() == {"detail": submission_service.DAILY_LIMIT_MESSAGE}
    assert db.query(Submission).count() == 2


def test_retry_counts_against_quota(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "ROAST_DAILY_LIMIT", 1)
    failed = add_pending(db, status=SubmissionStatus.failed, share_slug="failed-one")
    db.add(RoastAttempt(client_key=TEST_CLIENT_KEY, submission_id=failed.id))
    db.commit()
    response = client.post(f"{URL}/failed-one/retry")
    assert response.status_code == 429
    assert response.json() == {"detail": submission_service.DAILY_LIMIT_MESSAGE}
    assert by_slug(db, "failed-one").status == SubmissionStatus.failed
    assert db.query(RoastAttempt).count() == 1


@pytest.mark.usefixtures("rate_limiting")
def test_create_rate_limited(client: TestClient) -> None:
    statuses = [create(client, "bad-url").status_code for _ in range(11)]
    assert statuses[:10] == [400] * 10
    assert statuses[10] == 429


# ---------------------------------------------------------------------------- retry + lookup


@pytest.mark.parametrize(
    "status",
    [
        SubmissionStatus.pending,
        SubmissionStatus.analyzing,
        SubmissionStatus.roasting,
        SubmissionStatus.completed,
    ],
)
def test_retry_conflict_when_not_failed(
    client: TestClient, db: Session, status: SubmissionStatus
) -> None:
    add_pending(db, status=status, share_slug="not-failed")
    response = client.post(f"{URL}/not-failed/retry")
    assert response.status_code == 409
    assert response.json() == {"detail": submission_service.RETRY_CONFLICT_MESSAGE}


def test_unknown_slug_404(client: TestClient) -> None:
    assert client.get(f"{URL}/does-not-exist").status_code == 404
    assert client.post(f"{URL}/does-not-exist/retry").status_code == 404


def test_legacy_private_roast_stays_hidden(
    client: TestClient, completed_submission_factory: Callable[..., Submission]
) -> None:
    private = completed_submission_factory(is_public=False)
    assert client.get(f"{URL}/{private.share_slug}").status_code == 404
    assert client.post(f"{URL}/{private.share_slug}/retry").status_code == 404


# ---------------------------------------------------------------------------- misc service paths


def test_share_slug_collision_retries(
    db: Session,
    completed_submission_factory: Callable[..., Submission],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    existing = completed_submission_factory(share_slug="taken-slug")
    slugs = iter([existing.share_slug, "fresh-slug"])
    monkeypatch.setattr(submission_service, "_generate_share_slug", lambda: next(slugs))
    sub = submission_service.create_submission(db, TEST_CLIENT_KEY, "https://github.com/a/b")
    assert sub.share_slug == "fresh-slug"
    assert sub.status == SubmissionStatus.pending


def test_share_slug_collision_gives_up(
    db: Session,
    completed_submission_factory: Callable[..., Submission],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    completed_submission_factory(share_slug="always-taken")
    monkeypatch.setattr(submission_service, "_generate_share_slug", lambda: "always-taken")
    with pytest.raises(IntegrityError):
        submission_service.create_submission(db, TEST_CLIENT_KEY, "https://github.com/a/b")


def test_fail_stale_submissions(db: Session) -> None:
    old = datetime.now(UTC) - timedelta(minutes=30)
    stale = {
        status: add_pending(db, status=status, share_slug=f"stale-{status}")
        for status in (
            SubmissionStatus.pending,
            SubmissionStatus.analyzing,
            SubmissionStatus.roasting,
            SubmissionStatus.completed,
        )
    }
    fresh = add_pending(db, status=SubmissionStatus.analyzing, share_slug="fresh")
    db.execute(
        update(Submission)
        .where(Submission.id.in_([s.id for s in stale.values()]))
        .values(updated_at=old)
    )
    db.commit()

    assert fail_stale_submissions() == 3
    db.expire_all()
    for status in (SubmissionStatus.pending, SubmissionStatus.analyzing, SubmissionStatus.roasting):
        row = db.get(Submission, stale[status].id)
        assert row is not None
        assert row.status == SubmissionStatus.failed
        assert row.error_message == STALE_FAILURE_MESSAGE
    completed = db.get(Submission, stale[SubmissionStatus.completed].id)
    assert completed is not None and completed.status == SubmissionStatus.completed
    still = db.get(Submission, fresh.id)
    assert still is not None and still.status == SubmissionStatus.analyzing
    assert fail_stale_submissions() == 0


def test_lifespan_survives_stale_check_failure(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app import main

    def broken(**_kwargs: object) -> int:
        raise RuntimeError("db down")

    monkeypatch.setattr(main, "fail_stale_submissions", broken)
    with TestClient(main.app) as client:
        assert client.get("/health").status_code == 200


def test_lifespan_reports_stale_count(db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    from app import main

    calls: list[object] = []

    def fake(**kwargs: object) -> int:
        calls.append(kwargs.get("max_age", "default"))
        return 2

    monkeypatch.setattr(main, "fail_stale_submissions", fake)
    with TestClient(main.app) as client:
        assert client.get("/health").status_code == 200
    assert calls == [None]  # startup fails every non-terminal submission, regardless of age
