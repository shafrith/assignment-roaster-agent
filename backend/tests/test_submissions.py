"""Submission endpoints and the background pipeline (GitHub fixture repos + fake Claude)."""

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
from sqlalchemy.orm import Session

from app.config import settings
from app.models.repo_analysis import RepoAnalysis
from app.models.roast import Roast
from app.models.roast_attempt import RoastAttempt
from app.models.submission import Submission, SubmissionStatus
from app.models.user import User
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
from tests.conftest import headers_for
from tests.support import (
    FIXTURE_SECRETS,
    FakeAnthropic,
    FixtureRepo,
    mock_github_repos,
    roast_input,
    tool_response,
)

URL = "/api/v1/submissions"


def create(client: TestClient, headers: dict[str, str], repo_url: str) -> httpx.Response:
    return client.post(URL, json={"repoUrl": repo_url}, headers=headers)


def add_pending(db: Session, user: User, **overrides: Any) -> Submission:
    fields: dict[str, Any] = {
        "user_id": user.id,
        "repo_url": "https://github.com/eval-fixtures/clean_repo",
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
    user: User,
    auth_headers: dict[str, str],
    github_mock: respx.MockRouter,
    fake_claude: FakeAnthropic,
) -> None:
    repo = FixtureRepo("clean_repo")
    mock_github_repos(github_mock, repo)

    response = create(client, auth_headers, repo.url + ".git")
    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "pending"
    assert body["repoUrl"] == "https://github.com/eval-fixtures/clean_repo"
    assert body["repoOwner"] == "eval-fixtures"
    assert body["repoName"] == "clean_repo"
    assert body["isPublic"] is True
    assert body["analysis"] is None and body["roast"] is None
    assert len(body["shareSlug"]) >= 8

    # TestClient runs background tasks before returning, so the pipeline is done.
    detail = client.get(f"{URL}/{body['id']}", headers=auth_headers)
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
    assert "has_readme" not in detail.text  # camelCase on the wire

    assert fake_claude.call_count == 1
    prompt = fake_claude.messages.calls[0]["messages"][0]["content"]
    assert "app/llm.py" in prompt

    db.expire_all()
    sub = db.get(Submission, body["id"])
    assert sub is not None
    assert sub.commit_sha == repo.head_sha
    assert sub.default_branch == "main"
    assert sub.roast is not None and sub.roast.input_tokens == 1000
    assert sub.analysis is not None and "README.md" in sub.analysis.sampled_files


def test_messy_repo_secrets_never_stored_or_sent(
    client: TestClient,
    db: Session,
    auth_headers: dict[str, str],
    github_mock: respx.MockRouter,
    fake_claude: FakeAnthropic,
) -> None:
    repo = FixtureRepo("messy_repo")
    mock_github_repos(github_mock, repo)
    fake_claude.set_outputs(tool_response(roast_input(score=8.0)))

    submission_id = create(client, auth_headers, repo.url).json()["id"]
    done = client.get(f"{URL}/{submission_id}", headers=auth_headers).json()
    assert done["status"] == "completed"
    assert done["roast"]["score"] == 4.0  # committed-secret cap
    assert done["analysis"]["hasEnvFileCommitted"] is True
    assert done["analysis"]["secretsFoundCount"] > 0
    critical = [i for i in done["roast"]["issues"] if i["severity"] == "critical"]
    assert ".env" in {i["file"] for i in critical}

    prompt = fake_claude.messages.calls[0]["messages"][0]["content"]
    analysis_row = db.scalar(
        select(RepoAnalysis).where(RepoAnalysis.submission_id == submission_id)
    )
    stored = json.dumps(
        {c.key: getattr(analysis_row, c.key) for c in RepoAnalysis.__table__.columns},
        default=str,
    )
    for secret in FIXTURE_SECRETS:
        assert secret not in prompt
        assert secret not in stored
        assert secret not in json.dumps(done)
    assert "[REDACTED_SECRET]" in prompt


def test_create_defaults_visibility_from_user_setting(
    client: TestClient,
    user_factory: Callable[..., User],
    github_mock: respx.MockRouter,
    fake_claude: FakeAnthropic,
) -> None:
    mock_github_repos(github_mock, FixtureRepo("clean_repo"))
    private_by_default = user_factory(default_roast_public=False)
    response = create(
        client, headers_for(private_by_default), "https://github.com/eval-fixtures/clean_repo"
    )
    assert response.json()["isPublic"] is False


@pytest.mark.parametrize(
    "repo_url",
    [
        "https://gitlab.com/a/b",
        "https://github.com/settings/x",
        "not a url",
        "https://evil.com/a/b",
    ],
)
def test_create_invalid_url(
    client: TestClient, db: Session, auth_headers: dict[str, str], repo_url: str
) -> None:
    response = create(client, auth_headers, repo_url)
    assert response.status_code == 400
    assert response.json() == {"detail": INVALID_URL_MESSAGE}
    assert db.query(Submission).count() == 0


@pytest.mark.parametrize("body", [{}, {"repoUrl": ""}, {"repoUrl": "x" * 501}])
def test_create_validation(client: TestClient, auth_headers: dict[str, str], body: dict) -> None:
    assert client.post(URL, json=body, headers=auth_headers).status_code == 422


@pytest.mark.parametrize("private_style", ["flag", "404"])
def test_private_repo_fails_with_tanglish_message(
    client: TestClient,
    db: Session,
    auth_headers: dict[str, str],
    github_mock: respx.MockRouter,
    fake_claude: FakeAnthropic,
    private_style: str,
) -> None:
    if private_style == "flag":
        mock_github_repos(github_mock, FixtureRepo("clean_repo", owner="someone", private=True))
    else:
        mock_github_repos(github_mock)
    submission_id = create(client, auth_headers, "https://github.com/someone/clean_repo").json()[
        "id"
    ]
    done = client.get(f"{URL}/{submission_id}", headers=auth_headers).json()
    assert done["status"] == "failed"
    assert done["errorMessage"] == RepoNotFoundError.default_detail
    assert fake_claude.call_count == 0


def test_repo_too_large_fails(
    client: TestClient,
    auth_headers: dict[str, str],
    github_mock: respx.MockRouter,
    fake_claude: FakeAnthropic,
) -> None:
    repo = FixtureRepo("clean_repo", size_kb=settings.max_repo_size_kb + 1)
    mock_github_repos(github_mock, repo)
    submission_id = create(client, auth_headers, repo.url).json()["id"]
    done = client.get(f"{URL}/{submission_id}", headers=auth_headers).json()
    assert done["status"] == "failed"
    assert "MB" in done["errorMessage"]


def test_github_outage_fails(
    client: TestClient,
    auth_headers: dict[str, str],
    github_mock: respx.MockRouter,
    fake_claude: FakeAnthropic,
) -> None:
    github_mock.route(host="api.github.com").respond(503)
    submission_id = create(client, auth_headers, "https://github.com/a/b").json()["id"]
    done = client.get(f"{URL}/{submission_id}", headers=auth_headers).json()
    assert done["status"] == "failed"
    assert done["errorMessage"] == GitHubUnavailableError.default_detail


def test_claude_failure_then_retry_succeeds(
    client: TestClient,
    db: Session,
    auth_headers: dict[str, str],
    github_mock: respx.MockRouter,
    fake_claude: FakeAnthropic,
) -> None:
    repo = FixtureRepo("clean_repo")
    mock_github_repos(github_mock, repo)
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    fake_claude.set_outputs(anthropic.APITimeoutError(request=request), tool_response())

    submission_id = create(client, auth_headers, repo.url).json()["id"]
    failed = client.get(f"{URL}/{submission_id}", headers=auth_headers).json()
    assert failed["status"] == "failed"
    assert failed["errorMessage"] == RoastGenerationError.default_detail
    assert failed["roast"] is None

    retried = client.post(f"{URL}/{submission_id}/retry", headers=auth_headers)
    assert retried.status_code == 202
    assert retried.json()["status"] == "pending"
    assert retried.json()["errorMessage"] is None

    done = client.get(f"{URL}/{submission_id}", headers=auth_headers).json()
    assert done["status"] == "completed"
    assert done["roast"]["score"] == 7.5
    assert fake_claude.call_count == 2
    assert db.query(RepoAnalysis).count() == 1


def test_unexpected_pipeline_error_uses_generic_message(
    client: TestClient,
    auth_headers: dict[str, str],
    github_mock: respx.MockRouter,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_github_repos(github_mock, FixtureRepo("clean_repo"))

    async def explode(*_args: object) -> None:
        raise RuntimeError("internal detail that must not leak")

    monkeypatch.setattr(pipeline, "analyze_repo", explode)
    submission_id = create(client, auth_headers, "https://github.com/eval-fixtures/clean_repo")
    done = client.get(f"{URL}/{submission_id.json()['id']}", headers=auth_headers).json()
    assert done["status"] == "failed"
    assert done["errorMessage"] == GENERIC_FAILURE_MESSAGE


def test_dedupe_reuses_existing_roast(
    client: TestClient,
    db: Session,
    user_factory: Callable[..., User],
    github_mock: respx.MockRouter,
    fake_claude: FakeAnthropic,
) -> None:
    repo = FixtureRepo("clean_repo")
    mock_github_repos(github_mock, repo)
    first_user, second_user = user_factory(), user_factory()

    first_id = create(client, headers_for(first_user), repo.url).json()["id"]
    contents_after_first = len(repo.content_requests)
    second = create(client, headers_for(second_user), "https://github.com/EVAL-FIXTURES/Clean_Repo")
    second_id = second.json()["id"]

    assert fake_claude.call_count == 1  # second submission reused the roast
    assert len(repo.content_requests) == contents_after_first  # and the analysis
    a = client.get(f"{URL}/{first_id}", headers=headers_for(first_user)).json()
    b = client.get(f"{URL}/{second_id}", headers=headers_for(second_user)).json()
    assert b["status"] == "completed"
    assert b["roast"]["score"] == a["roast"]["score"]
    assert b["roast"]["verdictTitle"] == a["roast"]["verdictTitle"]
    assert b["analysis"] == a["analysis"]
    assert b["shareSlug"] != a["shareSlug"]
    assert db.query(Roast).count() == 2
    db.expire_all()
    copy = db.get(Submission, second_id)
    assert copy is not None and copy.deduped_from_submission_id == first_id
    assert copy.roast is not None
    assert (copy.roast.input_tokens, copy.roast.output_tokens) == (0, 0)  # no Claude spend


def test_new_commit_is_not_deduped(
    client: TestClient,
    db: Session,
    user: User,
    auth_headers: dict[str, str],
    github_mock: respx.MockRouter,
    fake_claude: FakeAnthropic,
) -> None:
    repo = FixtureRepo("clean_repo")
    mock_github_repos(github_mock, repo)
    create(client, auth_headers, repo.url)
    repo.head_sha = "f" * 40
    create(client, auth_headers, repo.url)
    assert fake_claude.call_count == 2


# ---------------------------------------------------------------------------- run_pipeline direct


async def test_run_pipeline_missing_or_not_pending(db: Session, user: User) -> None:
    await run_pipeline(987_654)  # deleted submission: no error
    sub = add_pending(db, user, status=SubmissionStatus.completed)
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


def test_daily_quota(
    client: TestClient,
    db: Session,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
    github_mock: respx.MockRouter,
    fake_claude: FakeAnthropic,
) -> None:
    mock_github_repos(github_mock, FixtureRepo("clean_repo"))
    monkeypatch.setattr(settings, "ROAST_DAILY_LIMIT", 2)
    url = "https://github.com/eval-fixtures/clean_repo"
    assert create(client, auth_headers, url).status_code == 202
    assert create(client, auth_headers, url).status_code == 202
    blocked = create(client, auth_headers, url)
    assert blocked.status_code == 429
    assert blocked.json() == {"detail": submission_service.DAILY_LIMIT_MESSAGE}
    assert db.query(Submission).count() == 2


def test_daily_quota_ignores_old_submissions(
    client: TestClient,
    db: Session,
    user: User,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "ROAST_DAILY_LIMIT", 1)
    old = add_pending(db, user, status=SubmissionStatus.failed)
    db.execute(
        update(Submission)
        .where(Submission.id == old.id)
        .values(created_at=datetime.now(UTC) - timedelta(hours=25))
    )
    db.commit()
    with respx.mock(assert_all_called=False) as router:
        router.route(host="api.github.com").respond(404)
        assert create(client, auth_headers, "https://github.com/a/b").status_code == 202


def test_retry_counts_against_quota(
    client: TestClient,
    db: Session,
    user: User,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "ROAST_DAILY_LIMIT", 1)
    failed = add_pending(db, user, status=SubmissionStatus.failed)
    db.add(RoastAttempt(user_id=user.id, submission_id=failed.id))
    db.commit()
    response = client.post(f"{URL}/{failed.id}/retry", headers=auth_headers)
    assert response.status_code == 429
    assert response.json() == {"detail": submission_service.DAILY_LIMIT_MESSAGE}
    db.expire_all()
    row = db.get(Submission, failed.id)
    assert row is not None and row.status == SubmissionStatus.failed
    assert db.query(RoastAttempt).count() == 1


@pytest.mark.usefixtures("rate_limiting")
def test_create_rate_limited(client: TestClient, db: Session, auth_headers: dict[str, str]) -> None:
    statuses = [create(client, auth_headers, "bad-url").status_code for _ in range(11)]
    assert statuses[:10] == [400] * 10
    assert statuses[10] == 429


# ---------------------------------------------------------------------------- retry


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
    client: TestClient, db: Session, user: User, auth_headers: dict[str, str], status: str
) -> None:
    sub = add_pending(db, user, status=status)
    response = client.post(f"{URL}/{sub.id}/retry", headers=auth_headers)
    assert response.status_code == 409
    assert response.json() == {"detail": submission_service.RETRY_CONFLICT_MESSAGE}


# ------------------------------------------------------------------ list / visibility / delete


def test_list_pagination(
    client: TestClient,
    db: Session,
    user: User,
    auth_headers: dict[str, str],
    user_factory: Callable[..., User],
    completed_submission_factory: Callable[..., Submission],
) -> None:
    roasted = completed_submission_factory(user)
    for _ in range(4):
        add_pending(db, user, share_slug=f"p{db.query(Submission).count()}")
    completed_submission_factory(user_factory())  # someone else's

    page1 = client.get(URL, params={"page": 1, "pageSize": 2}, headers=auth_headers).json()
    assert page1["total"] == 5
    assert page1["page"] == 1
    assert page1["pageSize"] == 2
    assert len(page1["items"]) == 2
    page3 = client.get(URL, params={"page": 3, "pageSize": 2}, headers=auth_headers).json()
    assert len(page3["items"]) == 1
    assert page3["items"][0]["id"] == roasted.id  # oldest last (newest first ordering)
    assert page3["items"][0]["score"] == 6.5
    assert page3["items"][0]["verdictTitle"] == "Notebook Nayagan"
    assert page1["items"][0]["score"] is None
    assert set(page1["items"][0]) == {
        "id",
        "repoOwner",
        "repoName",
        "status",
        "score",
        "verdictTitle",
        "isPublic",
        "createdAt",
    }
    beyond = client.get(URL, params={"page": 10}, headers=auth_headers).json()
    assert beyond["items"] == [] and beyond["total"] == 5
    default = client.get(URL, headers=auth_headers).json()
    assert default["pageSize"] == 10 and len(default["items"]) == 5


@pytest.mark.parametrize("params", [{"pageSize": 0}, {"pageSize": 51}, {"page": 0}, {"page": "x"}])
def test_list_bounds(client: TestClient, auth_headers: dict[str, str], params: dict) -> None:
    assert client.get(URL, params=params, headers=auth_headers).status_code == 422


def test_list_page_size_max_ok(client: TestClient, auth_headers: dict[str, str]) -> None:
    assert client.get(URL, params={"pageSize": 50}, headers=auth_headers).status_code == 200


def test_visibility_toggle(
    client: TestClient,
    user: User,
    auth_headers: dict[str, str],
    completed_submission_factory: Callable[..., Submission],
) -> None:
    sub = completed_submission_factory(user)
    response = client.patch(
        f"{URL}/{sub.id}/visibility", json={"isPublic": False}, headers=auth_headers
    )
    assert response.status_code == 200
    assert response.json()["isPublic"] is False
    assert client.get(f"/api/v1/public/roasts/{sub.share_slug}").status_code == 404
    client.patch(f"{URL}/{sub.id}/visibility", json={"isPublic": True}, headers=auth_headers)
    assert client.get(f"/api/v1/public/roasts/{sub.share_slug}").status_code == 200
    bad = client.patch(f"{URL}/{sub.id}/visibility", json={}, headers=auth_headers)
    assert bad.status_code == 422


def test_delete(
    client: TestClient,
    db: Session,
    user: User,
    auth_headers: dict[str, str],
    completed_submission_factory: Callable[..., Submission],
) -> None:
    sub_id = completed_submission_factory(user).id
    assert client.delete(f"{URL}/{sub_id}", headers=auth_headers).status_code == 204
    assert client.get(f"{URL}/{sub_id}", headers=auth_headers).status_code == 404
    db.expire_all()
    assert db.query(Roast).count() == 0
    assert db.query(RepoAnalysis).count() == 0
    assert client.delete(f"{URL}/{sub_id}", headers=auth_headers).status_code == 404


def test_other_users_submission_is_404(
    client: TestClient,
    db: Session,
    user_factory: Callable[..., User],
    completed_submission_factory: Callable[..., Submission],
) -> None:
    owner, intruder = user_factory(), user_factory()
    sub = completed_submission_factory(owner, status=SubmissionStatus.failed)
    headers = headers_for(intruder)
    responses = [
        client.get(f"{URL}/{sub.id}", headers=headers),
        client.patch(f"{URL}/{sub.id}/visibility", json={"isPublic": False}, headers=headers),
        client.post(f"{URL}/{sub.id}/retry", headers=headers),
        client.delete(f"{URL}/{sub.id}", headers=headers),
    ]
    for response in responses:
        assert response.status_code == 404
        assert response.json() == {"detail": submission_service.NOT_FOUND_MESSAGE}
    assert client.get(URL, headers=headers).json()["total"] == 0
    db.expire_all()
    still_there = db.get(Submission, sub.id)
    assert still_there is not None and still_there.is_public
    assert still_there.status == SubmissionStatus.failed


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", URL),
        ("post", URL),
        ("get", f"{URL}/1"),
        ("post", f"{URL}/1/retry"),
        ("patch", f"{URL}/1/visibility"),
        ("delete", f"{URL}/1"),
    ],
)
def test_unauthenticated_401(client: TestClient, method: str, path: str) -> None:
    response = client.request(method, path, json={"repoUrl": "https://github.com/a/b"})
    assert response.status_code == 401


def test_unknown_submission_404(client: TestClient, auth_headers: dict[str, str]) -> None:
    assert client.get(f"{URL}/999999", headers=auth_headers).status_code == 404


# ---------------------------------------------------------------------------- misc service paths


def test_share_slug_collision_retries(
    db: Session,
    user: User,
    completed_submission_factory: Callable[..., Submission],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    existing = completed_submission_factory(user, share_slug="taken-slug")
    slugs = iter([existing.share_slug, "fresh-slug"])
    monkeypatch.setattr(submission_service, "_generate_share_slug", lambda: next(slugs))
    sub = submission_service.create_submission(db, user, "https://github.com/a/b")
    assert sub.share_slug == "fresh-slug"
    assert sub.status == SubmissionStatus.pending


def test_share_slug_collision_gives_up(
    db: Session,
    user: User,
    completed_submission_factory: Callable[..., Submission],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from sqlalchemy.exc import IntegrityError

    completed_submission_factory(user, share_slug="always-taken")
    monkeypatch.setattr(submission_service, "_generate_share_slug", lambda: "always-taken")
    with pytest.raises(IntegrityError):
        submission_service.create_submission(db, user, "https://github.com/a/b")


def test_fail_stale_submissions(db: Session, user: User) -> None:
    old = datetime.now(UTC) - timedelta(minutes=30)
    stale = {
        status: add_pending(db, user, status=status, share_slug=f"stale-{status}")
        for status in (
            SubmissionStatus.pending,
            SubmissionStatus.analyzing,
            SubmissionStatus.roasting,
            SubmissionStatus.completed,
        )
    }
    fresh = add_pending(db, user, status=SubmissionStatus.analyzing, share_slug="fresh")
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
