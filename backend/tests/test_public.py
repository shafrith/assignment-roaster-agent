"""Public share page: no auth, never leaks private fields, 404 unless public + completed."""

from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.submission import Submission, SubmissionStatus
from app.models.user import User
from app.services.submission_service import NOT_FOUND_MESSAGE


def public_url(slug: str) -> str:
    return f"/api/v1/public/roasts/{slug}"


def test_public_roast_without_auth(
    client: TestClient,
    user: User,
    completed_submission_factory: Callable[..., Submission],
) -> None:
    sub = completed_submission_factory(user)
    response = client.get(public_url(sub.share_slug))
    assert response.status_code == 200
    body = response.json()
    assert body["repoUrl"] == sub.repo_url
    assert body["repoOwner"] == sub.repo_owner
    assert body["repoName"] == sub.repo_name
    assert body["author"] == {
        "githubUsername": user.github_username,
        "avatarUrl": user.avatar_url,
    }
    assert body["roast"]["score"] == 6.5
    assert body["roast"]["verdictTitle"] == "Notebook Nayagan"
    assert body["analysis"]["fileCount"] == 3
    assert "createdAt" in body


def test_public_roast_never_exposes_private_fields(
    client: TestClient,
    user_factory: Callable[..., User],
    completed_submission_factory: Callable[..., Submission],
) -> None:
    owner = user_factory(email="very-private@example.com", display_name="Private Name")
    sub = completed_submission_factory(owner)
    response = client.get(public_url(sub.share_slug))
    text = response.text
    assert "very-private@example.com" not in text
    assert "@example.com" not in text
    assert "email" not in text.lower()
    for private_key in ("userId", "isPublic", "errorMessage", "inputTokens", "model", "shareSlug"):
        assert f'"{private_key}"' not in text
    # Owner-only analysis facts: the public page must not index repos with leaked secrets.
    assert "secretsFoundCount" not in response.json()["analysis"]
    assert "hasEnvFileCommitted" not in response.json()["analysis"]
    assert "id" not in response.json()["author"]


def test_private_roast_404(
    client: TestClient, user: User, completed_submission_factory: Callable[..., Submission]
) -> None:
    sub = completed_submission_factory(user, is_public=False)
    response = client.get(public_url(sub.share_slug))
    assert response.status_code == 404
    assert response.json() == {"detail": NOT_FOUND_MESSAGE}


@pytest.mark.parametrize(
    "status",
    [
        SubmissionStatus.pending,
        SubmissionStatus.analyzing,
        SubmissionStatus.roasting,
        SubmissionStatus.failed,
    ],
)
def test_not_completed_404(
    client: TestClient,
    user: User,
    completed_submission_factory: Callable[..., Submission],
    status: SubmissionStatus,
) -> None:
    sub = completed_submission_factory(user, status=status)
    assert client.get(public_url(sub.share_slug)).status_code == 404


def test_completed_without_roast_404(
    client: TestClient,
    db: Session,
    user: User,
    completed_submission_factory: Callable[..., Submission],
) -> None:
    sub = completed_submission_factory(user)
    assert sub.roast is not None
    db.delete(sub.roast)
    db.commit()
    assert client.get(public_url(sub.share_slug)).status_code == 404


@pytest.mark.parametrize("slug", ["does-not-exist", "x" * 200, "%27%20OR%201%3D1--"])
def test_unknown_slug_404(client: TestClient, db: Session, slug: str) -> None:
    assert client.get(public_url(slug)).status_code == 404


def test_public_roast_ignores_bad_auth_header(
    client: TestClient, user: User, completed_submission_factory: Callable[..., Submission]
) -> None:
    sub = completed_submission_factory(user)
    response = client.get(public_url(sub.share_slug), headers={"Authorization": "Bearer junk"})
    assert response.status_code == 200
