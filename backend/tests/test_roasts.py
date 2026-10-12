"""No-login roast endpoints: create by URL, poll by share slug, retry (fixture repos + fake Claude)."""

from collections.abc import Callable

import anthropic
import httpx
import pytest
import respx
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import settings
from app.models.roast_attempt import RoastAttempt
from app.models.submission import Submission, SubmissionStatus
from app.models.user import User
from app.services import submission_service
from app.services.contracts import RoastGenerationError
from app.services.github_url import INVALID_URL_MESSAGE
from tests.support import FakeAnthropic, FixtureRepo, mock_github_repos, tool_response

URL = "/api/v1/roasts"
REPO_URL = "https://github.com/eval-fixtures/clean_repo"


def create(client: TestClient, repo_url: str = REPO_URL) -> httpx.Response:
    return client.post(URL, json={"repoUrl": repo_url})


def test_create_without_login_runs_pipeline(
    client: TestClient,
    db: Session,
    github_mock: respx.MockRouter,
    fake_claude: FakeAnthropic,
) -> None:
    mock_github_repos(github_mock, FixtureRepo("clean_repo"))

    response = create(client, REPO_URL + ".git")
    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "pending"
    assert body["repoUrl"] == REPO_URL
    assert body["author"] is None
    assert body["roast"] is None
    assert "id" not in body
    slug = body["shareSlug"]
    assert len(slug) >= 10

    done = client.get(f"{URL}/{slug}")
    assert done.status_code == 200
    result = done.json()
    assert result["status"] == "completed"
    assert result["roast"]["score"] == 7.5
    assert "secretsFoundCount" not in result["analysis"]
    assert "hasEnvFileCommitted" not in result["analysis"]

    submission = db.query(Submission).one()
    assert submission.user_id is None
    assert submission.is_public is True
    attempt = db.query(RoastAttempt).one()
    assert attempt.user_id is None
    assert attempt.client_key is not None and len(attempt.client_key) == 64
    assert "testclient" not in attempt.client_key  # raw client address is never stored

    # The completed anonymous roast is also reachable on the public share endpoint.
    shared = client.get(f"/api/v1/public/roasts/{slug}")
    assert shared.status_code == 200
    assert shared.json()["author"] is None


def test_create_invalid_url(client: TestClient, db: Session) -> None:
    response = create(client, "https://gitlab.com/a/b")
    assert response.status_code == 400
    assert response.json() == {"detail": INVALID_URL_MESSAGE}
    assert db.query(Submission).count() == 0


def test_in_progress_roast_hides_partial_results(client: TestClient, db: Session) -> None:
    submission = Submission(
        repo_url=REPO_URL,
        repo_owner="eval-fixtures",
        repo_name="clean_repo",
        status=SubmissionStatus.roasting,
        share_slug="anon-in-progress",
    )
    db.add(submission)
    db.commit()
    body = client.get(f"{URL}/anon-in-progress").json()
    assert body["status"] == "roasting"
    assert body["analysis"] is None
    assert body["roast"] is None


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


def test_failure_then_retry_succeeds(
    client: TestClient,
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
    assert failed["errorRetryable"] is True

    retried = client.post(f"{URL}/{slug}/retry")
    assert retried.status_code == 202
    assert retried.json()["status"] == "pending"

    done = client.get(f"{URL}/{slug}").json()
    assert done["status"] == "completed"
    assert fake_claude.call_count == 2


def test_retry_conflict_when_not_failed(
    client: TestClient,
    github_mock: respx.MockRouter,
    fake_claude: FakeAnthropic,
) -> None:
    mock_github_repos(github_mock, FixtureRepo("clean_repo"))
    slug = create(client).json()["shareSlug"]
    response = client.post(f"{URL}/{slug}/retry")
    assert response.status_code == 409
    assert response.json() == {"detail": submission_service.RETRY_CONFLICT_MESSAGE}


def test_unknown_slug_404(client: TestClient) -> None:
    assert client.get(f"{URL}/does-not-exist").status_code == 404
    assert client.post(f"{URL}/does-not-exist/retry").status_code == 404


def test_user_owned_roasts(
    client: TestClient,
    db: Session,
    user: User,
    completed_submission_factory: Callable[..., Submission],
) -> None:
    public = completed_submission_factory(user)
    private = completed_submission_factory(user, is_public=False)

    body = client.get(f"{URL}/{public.share_slug}").json()
    assert body["author"] == {
        "githubUsername": user.github_username,
        "avatarUrl": user.avatar_url,
    }
    # A private user-owned roast is not leaked, and nobody can retry someone's roast anonymously.
    assert client.get(f"{URL}/{private.share_slug}").status_code == 404
    assert client.post(f"{URL}/{public.share_slug}/retry").status_code == 404


@pytest.mark.usefixtures("rate_limiting")
def test_create_rate_limited(client: TestClient) -> None:
    statuses = [create(client, "bad-url").status_code for _ in range(11)]
    assert statuses[:10] == [400] * 10
    assert statuses[10] == 429
