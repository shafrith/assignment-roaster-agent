"""GitHub OAuth login, JWT access tokens, refresh rotation, logout, and profile endpoints."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlsplit

import httpx
import jwt
import pytest
import respx
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.jwt import (
    INVALID_TOKEN_MESSAGE,
    JWT_ALGORITHM,
    create_access_token,
    create_oauth_state,
    hash_token,
    nonces_match,
    verify_oauth_state,
)
from app.config import settings
from app.dependencies import get_current_user_optional
from app.exceptions import RATE_LIMIT_MESSAGE, UnauthorizedError, UpstreamError
from app.models.refresh_token import RefreshToken
from app.models.roast_attempt import RoastAttempt
from app.models.user import User
from app.services import auth_service, github_oauth
from tests.conftest import headers_for

LOGIN = "/api/v1/auth/github/login"
CALLBACK = "/api/v1/auth/github/callback"
TOKEN_URL = "https://github.com/login/oauth/access_token"
GH_USER = {
    "id": 4242,
    "login": "kavya-codes",
    "name": "Kavya",
    "avatar_url": "https://avatars.githubusercontent.com/u/4242",
    "email": None,
}
FRONTEND = settings.FRONTEND_URL


def start_login(client: TestClient) -> str:
    """Hit the login endpoint (sets the state cookie) and return the signed state."""
    response = client.get(LOGIN, follow_redirects=False)
    assert response.status_code == 302
    return parse_qs(urlsplit(response.headers["location"]).query)["state"][0]


def mock_github_oauth(
    router: respx.MockRouter,
    *,
    user: dict[str, object] | None = None,
    emails: list[dict[str, object]] | None = None,
) -> None:
    router.post(TOKEN_URL).respond(200, json={"access_token": "gho_test", "token_type": "bearer"})
    router.get("https://api.github.com/user").respond(200, json=user or GH_USER)
    router.get("https://api.github.com/user/emails").respond(
        200,
        json=emails
        if emails is not None
        else [
            {"email": "secondary@example.com", "primary": False, "verified": True},
            {"email": "kavya@example.com", "primary": True, "verified": True},
        ],
    )


def callback(client: TestClient, **params: str) -> httpx.Response:
    return client.get(CALLBACK, params=params, follow_redirects=False)


def error_code(response: httpx.Response) -> str:
    assert response.status_code == 302
    location = response.headers["location"]
    assert location.startswith(f"{FRONTEND}/login?")
    return parse_qs(urlsplit(location).query)["error"][0]


def fragment_tokens(response: httpx.Response) -> dict[str, str]:
    assert response.status_code == 302
    location = urlsplit(response.headers["location"])
    assert f"{location.scheme}://{location.netloc}{location.path}" == f"{FRONTEND}/auth/callback"
    assert location.query == ""
    return {k: v[0] for k, v in parse_qs(location.fragment).items()}


# ---------------------------------------------------------------------------- login


def test_login_redirects_to_github_with_state_cookie(client: TestClient) -> None:
    response = client.get(LOGIN, follow_redirects=False)
    assert response.status_code == 302
    location = urlsplit(response.headers["location"])
    assert f"{location.scheme}://{location.netloc}{location.path}" == (
        "https://github.com/login/oauth/authorize"
    )
    query = parse_qs(location.query)
    assert query["client_id"] == [settings.GITHUB_CLIENT_ID]
    assert query["scope"] == ["read:user user:email"]
    assert query["redirect_uri"] == [settings.GITHUB_REDIRECT_URI]
    nonce = verify_oauth_state(query["state"][0])
    cookie = response.headers["set-cookie"]
    assert f"oauth_state={nonce}" in cookie
    assert "HttpOnly" in cookie
    assert "Path=/api/v1/auth/github" in cookie
    assert "samesite=lax" in cookie.lower()


def test_login_not_configured(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "GITHUB_CLIENT_ID", "")
    assert error_code(client.get(LOGIN, follow_redirects=False)) == "github_error"


# ---------------------------------------------------------------------------- callback


def test_callback_success_creates_user_and_returns_tokens_in_fragment(
    client: TestClient, db: Session, github_mock: respx.MockRouter
) -> None:
    mock_github_oauth(github_mock)
    state = start_login(client)
    response = callback(client, code="abc", state=state)
    tokens = fragment_tokens(response)
    assert set(tokens) == {"access", "refresh"}
    assert "oauth_state=" in response.headers["set-cookie"]  # cookie cleared

    user = db.scalar(select(User).where(User.github_id == 4242))
    assert user is not None
    assert user.github_username == "kavya-codes"
    assert user.email == "kavya@example.com"  # primary verified address from /user/emails

    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {tokens['access']}"})
    assert me.status_code == 200
    body = me.json()
    assert body["githubUsername"] == "kavya-codes"
    assert body["defaultRoastPublic"] is True
    assert "email" not in body
    assert "kavya@example.com" not in me.text

    stored = db.scalar(select(RefreshToken).where(RefreshToken.user_id == user.id))
    assert stored is not None
    assert stored.token_hash == hash_token(tokens["refresh"])
    assert stored.token_hash != tokens["refresh"]


def test_callback_updates_existing_user(
    client: TestClient,
    db: Session,
    github_mock: respx.MockRouter,
    user_factory: Callable[..., User],
) -> None:
    existing = user_factory(github_id=4242, github_username="old-name")
    mock_github_oauth(github_mock, user={**GH_USER, "email": "public@example.com"})
    tokens = fragment_tokens(callback(client, code="abc", state=start_login(client)))
    assert tokens["access"]
    db.refresh(existing)
    assert existing.github_username == "kavya-codes"
    assert existing.email == "public@example.com"
    assert db.query(User).count() == 1


def test_callback_missing_cookie_is_invalid_state(client: TestClient) -> None:
    state = start_login(client)
    client.cookies.clear()
    assert error_code(callback(client, code="abc", state=state)) == "invalid_state"


def test_callback_mismatched_cookie_is_invalid_state(client: TestClient) -> None:
    start_login(client)
    other_state, _ = create_oauth_state()
    assert error_code(callback(client, code="abc", state=other_state)) == "invalid_state"


@pytest.mark.parametrize("tamper", ["tampered", "missing", "wrong_type", "expired"])
def test_callback_bad_state(client: TestClient, tamper: str) -> None:
    state = start_login(client)
    params = {"code": "abc"}
    if tamper == "tampered":
        params["state"] = state[:-3] + ("aaa" if not state.endswith("aaa") else "bbb")
    elif tamper == "wrong_type":
        params["state"] = create_access_token(1)
    elif tamper == "expired":
        now = datetime.now(UTC)
        params["state"] = jwt.encode(
            {"type": "oauth_state", "nonce": "n", "iat": now, "exp": now - timedelta(1)},
            settings.SECRET_KEY,
            algorithm=JWT_ALGORITHM,
        )
    assert error_code(callback(client, **params)) == "invalid_state"


def test_callback_user_denied(client: TestClient) -> None:
    assert error_code(callback(client, error="access_denied")) == "oauth_denied"


def test_callback_without_code(client: TestClient) -> None:
    assert error_code(callback(client, state=start_login(client))) == "oauth_denied"


@pytest.mark.parametrize(
    "token_response",
    [
        httpx.Response(200, json={"error": "bad_verification_code"}),
        httpx.Response(200, json={"token_type": "bearer"}),
        httpx.Response(200, text="not json"),
        httpx.Response(500, json={}),
    ],
)
def test_callback_github_error(
    client: TestClient, github_mock: respx.MockRouter, token_response: httpx.Response
) -> None:
    github_mock.post(TOKEN_URL).mock(return_value=token_response)
    assert error_code(callback(client, code="abc", state=start_login(client))) == "github_error"


def test_callback_inactive_user(
    client: TestClient, github_mock: respx.MockRouter, user_factory: Callable[..., User]
) -> None:
    user_factory(github_id=4242, is_active=False)
    mock_github_oauth(github_mock)
    assert error_code(callback(client, code="abc", state=start_login(client))) == "inactive"


# ---------------------------------------------------------------------------- github_oauth service


async def test_exchange_code_network_error(github_mock: respx.MockRouter) -> None:
    github_mock.post(TOKEN_URL).mock(side_effect=httpx.ConnectError("down"))
    with pytest.raises(UpstreamError):
        await github_oauth.exchange_code("abc")


@pytest.mark.parametrize(
    ("user_response", "expected"),
    [
        (httpx.Response(401, json={}), UnauthorizedError),
        (httpx.Response(500, json={}), UpstreamError),
        (httpx.Response(200, text="nope"), UpstreamError),
        (httpx.Response(200, json={"login": "x"}), UpstreamError),
    ],
)
async def test_fetch_github_user_errors(
    github_mock: respx.MockRouter, user_response: httpx.Response, expected: type[Exception]
) -> None:
    github_mock.get("https://api.github.com/user").mock(return_value=user_response)
    with pytest.raises(expected):
        await github_oauth.fetch_github_user("tok")


async def test_fetch_github_user_network_error(github_mock: respx.MockRouter) -> None:
    github_mock.get("https://api.github.com/user").mock(side_effect=httpx.ReadTimeout("slow"))
    with pytest.raises(UpstreamError):
        await github_oauth.fetch_github_user("tok")


@pytest.mark.parametrize(
    "emails_response",
    [
        httpx.Response(403, json={}),
        httpx.Response(200, json={"not": "a list"}),
        httpx.Response(200, json=[{"email": "x@example.com", "primary": True, "verified": False}]),
    ],
)
async def test_fetch_github_user_email_best_effort(
    github_mock: respx.MockRouter, emails_response: httpx.Response
) -> None:
    github_mock.get("https://api.github.com/user").respond(200, json=GH_USER)
    github_mock.get("https://api.github.com/user/emails").mock(return_value=emails_response)
    user = await github_oauth.fetch_github_user("tok")
    assert user["email"] is None
    assert user["login"] == "kavya-codes"


def test_upsert_rejects_bad_profile(db: Session) -> None:
    with pytest.raises(UpstreamError):
        auth_service.upsert_user_from_github(db, {"id": "1", "login": "x"})


def test_upsert_concurrent_first_login_falls_back_to_winner(
    db: Session, user_factory: Callable[..., User], monkeypatch: pytest.MonkeyPatch
) -> None:
    winner = user_factory(github_id=555, github_username="old")
    winner_id = winner.id
    real_scalar = db.scalar
    lookups: list[object] = []

    def racing_scalar(statement: object) -> object:
        # Simulate: our first SELECT ran before the other request's INSERT committed.
        lookups.append(statement)
        return None if len(lookups) == 1 else real_scalar(statement)

    monkeypatch.setattr(db, "scalar", racing_scalar)
    user = auth_service.upsert_user_from_github(db, {"id": 555, "login": "new-name"})
    assert user.id == winner_id
    assert user.github_username == "new-name"
    assert db.query(User).count() == 1


def test_upsert_clips_long_fields(db: Session) -> None:
    user = auth_service.upsert_user_from_github(
        db, {"id": 7, "login": "u" * 300, "name": "", "avatar_url": 5, "email": "e" * 400}
    )
    assert len(user.github_username) == 100
    assert user.display_name is None
    assert user.avatar_url is None
    assert user.email is not None and len(user.email) == 255


# ---------------------------------------------------------------------------- access tokens


def test_me_requires_auth(client: TestClient) -> None:
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json()["detail"]


def test_me_returns_profile_without_email(
    client: TestClient, user: User, auth_headers: dict[str, str]
) -> None:
    response = client.get("/api/v1/auth/me", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == user.id
    assert body["githubUsername"] == user.github_username
    assert body["displayName"] == user.display_name
    assert body["avatarUrl"] == user.avatar_url
    assert "createdAt" in body
    assert "email" not in body
    assert user.email is not None and user.email not in response.text
    assert body["dailyLimit"] == settings.ROAST_DAILY_LIMIT
    assert body["roastsUsedToday"] == 0


def test_me_reports_quota_usage(
    client: TestClient,
    db: Session,
    user: User,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "ROAST_DAILY_LIMIT", 7)
    db.add_all(
        [
            RoastAttempt(user_id=user.id),
            RoastAttempt(user_id=user.id),
            # Outside the 24h window: not counted.
            RoastAttempt(user_id=user.id, created_at=datetime.now(UTC) - timedelta(hours=25)),
        ]
    )
    db.commit()
    body = client.get("/api/v1/auth/me", headers=auth_headers).json()
    assert (body["dailyLimit"], body["roastsUsedToday"]) == (7, 2)
    patched = client.patch(
        "/api/v1/auth/me", json={"defaultRoastPublic": False}, headers=auth_headers
    ).json()
    assert (patched["dailyLimit"], patched["roastsUsedToday"]) == (7, 2)


def _token(claims: dict[str, object], algorithm: str = JWT_ALGORITHM) -> str:
    return jwt.encode(claims, settings.SECRET_KEY, algorithm=algorithm)


@pytest.mark.filterwarnings("ignore::jwt.warnings.InsecureKeyLengthWarning")
@pytest.mark.parametrize(
    "token_kind",
    [
        "expired",
        "garbage",
        "wrong_secret",
        "refresh_type",
        "bad_sub",
        "unknown_user",
        "missing_exp",
        "missing_type",
        "other_hmac_alg",
        "alg_none",
    ],
)
def test_invalid_access_tokens_401(client: TestClient, user: User, token_kind: str) -> None:
    now = datetime.now(UTC)
    later = now + timedelta(1)
    good: dict[str, object] = {"sub": str(user.id), "type": "access", "iat": now, "exp": later}
    tokens = {
        "expired": _token({**good, "exp": now - timedelta(1)}),
        "garbage": "not.a.jwt",
        "wrong_secret": jwt.encode(good, "other-secret-that-is-long-enough-123", "HS256"),
        "refresh_type": _token({**good, "type": "oauth_state", "nonce": "x"}),
        "bad_sub": _token({**good, "sub": "abc"}),
        "unknown_user": create_access_token(999_999),
        "missing_exp": _token({k: v for k, v in good.items() if k != "exp"}),
        "missing_type": _token({k: v for k, v in good.items() if k != "type"}),
        "other_hmac_alg": _token(good, algorithm="HS512"),
        "alg_none": jwt.encode(good, None, algorithm="none"),
    }
    response = client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {tokens[token_kind]}"}
    )
    assert response.status_code == 401
    assert response.json()["detail"] == INVALID_TOKEN_MESSAGE


def test_inactive_user_forbidden(client: TestClient, user_factory: Callable[..., User]) -> None:
    inactive = user_factory(is_active=False)
    response = client.get("/api/v1/auth/me", headers=headers_for(inactive))
    assert response.status_code == 403


async def test_get_current_user_optional(db: Session, user: User) -> None:
    from fastapi.security import HTTPAuthorizationCredentials

    def creds(token: str) -> HTTPAuthorizationCredentials:
        return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

    assert await get_current_user_optional(None, db) is None
    assert await get_current_user_optional(creds("junk"), db) is None
    resolved = await get_current_user_optional(creds(create_access_token(user.id)), db)
    assert resolved is not None and resolved.id == user.id


def test_nonces_match() -> None:
    assert nonces_match("abc", "abc")
    assert not nonces_match(None, "abc")
    assert not nonces_match("abc", "abd")


def test_update_settings(
    client: TestClient, db: Session, user: User, auth_headers: dict[str, str]
) -> None:
    response = client.patch(
        "/api/v1/auth/me", json={"defaultRoastPublic": False}, headers=auth_headers
    )
    assert response.status_code == 200
    assert response.json()["defaultRoastPublic"] is False
    db.refresh(user)
    assert user.default_roast_public is False
    bad = client.patch(
        "/api/v1/auth/me", json={"defaultRoastPublic": "maybe"}, headers=auth_headers
    )
    assert bad.status_code == 422


# ---------------------------------------------------------------------------- refresh / logout


def refresh(client: TestClient, token: str) -> httpx.Response:
    return client.post("/api/v1/auth/refresh", json={"refreshToken": token})


def test_refresh_rotates_tokens(client: TestClient, db: Session, user: User) -> None:
    first = auth_service.issue_tokens(db, user)
    response = refresh(client, first.refresh_token)
    assert response.status_code == 200
    body = response.json()
    assert body["tokenType"] == "bearer"
    assert body["refreshToken"] != first.refresh_token
    assert (
        client.get(
            "/api/v1/auth/me", headers={"Authorization": f"Bearer {body['accessToken']}"}
        ).status_code
        == 200
    )
    old = db.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == hash_token(first.refresh_token))
    )
    assert old is not None and old.revoked


def _stored(db: Session, raw_token: str) -> RefreshToken:
    db.expire_all()
    row = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == hash_token(raw_token)))
    assert row is not None
    return row


def test_refresh_reuse_revokes_all_sessions(client: TestClient, db: Session, user: User) -> None:
    other_session = auth_service.issue_tokens(db, user)
    first = auth_service.issue_tokens(db, user)
    rotated = refresh(client, first.refresh_token).json()
    # Replayed well after the rotation (outside the concurrent-tab grace window): theft.
    old = _stored(db, first.refresh_token)
    assert old.revoked_at is not None
    old.revoked_at = datetime.now(UTC) - auth_service.REFRESH_REUSE_GRACE - timedelta(seconds=1)
    db.commit()

    reuse = refresh(client, first.refresh_token)
    assert reuse.status_code == 401
    assert reuse.json()["detail"] == auth_service.TOKEN_REUSE_MESSAGE

    assert refresh(client, rotated["refreshToken"]).status_code == 401
    assert refresh(client, other_session.refresh_token).status_code == 401
    db.expire_all()
    active = db.query(RefreshToken).filter_by(user_id=user.id, revoked=False).count()
    assert active == 0


def test_concurrent_refresh_within_grace_keeps_sessions(
    client: TestClient, db: Session, user: User
) -> None:
    first = auth_service.issue_tokens(db, user)
    winner = refresh(client, first.refresh_token)
    assert winner.status_code == 200

    loser = refresh(client, first.refresh_token)  # second tab, same token, moments later
    assert loser.status_code == 401
    assert loser.json()["detail"] == auth_service.CONCURRENT_REFRESH_MESSAGE

    old = _stored(db, first.refresh_token)
    replacement = _stored(db, winner.json()["refreshToken"])
    assert old.replaced_by_id == replacement.id
    assert not replacement.revoked  # the winning tab keeps its session
    assert refresh(client, winner.json()["refreshToken"]).status_code == 200


def test_reuse_within_grace_after_replacement_used_is_theft(
    client: TestClient, db: Session, user: User
) -> None:
    first = auth_service.issue_tokens(db, user)
    second = refresh(client, first.refresh_token).json()
    third = refresh(client, second["refreshToken"]).json()  # replacement already rotated

    reuse = refresh(client, first.refresh_token)
    assert reuse.status_code == 401
    assert reuse.json()["detail"] == auth_service.TOKEN_REUSE_MESSAGE
    assert refresh(client, third["refreshToken"]).status_code == 401


def test_logged_out_token_reuse_is_theft(client: TestClient, db: Session, user: User) -> None:
    tokens = auth_service.issue_tokens(db, user)
    other = auth_service.issue_tokens(db, user)
    client.post("/api/v1/auth/logout", json={"refreshToken": tokens.refresh_token})
    assert _stored(db, tokens.refresh_token).revoked_at is not None
    response = refresh(client, tokens.refresh_token)
    assert response.json()["detail"] == auth_service.TOKEN_REUSE_MESSAGE
    assert refresh(client, other.refresh_token).status_code == 401


def test_refresh_unknown_token(client: TestClient, db: Session) -> None:
    response = refresh(client, "never-issued")
    assert response.status_code == 401
    assert response.json()["detail"] == auth_service.INVALID_REFRESH_MESSAGE


def test_refresh_expired_token(client: TestClient, db: Session, user: User) -> None:
    tokens = auth_service.issue_tokens(db, user)
    stored = db.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == hash_token(tokens.refresh_token))
    )
    assert stored is not None
    stored.expires_at = datetime.now(UTC) - timedelta(minutes=1)
    db.commit()
    response = refresh(client, tokens.refresh_token)
    assert response.status_code == 401
    assert response.json()["detail"] == auth_service.INVALID_REFRESH_MESSAGE


def test_refresh_inactive_user(client: TestClient, db: Session, user: User) -> None:
    tokens = auth_service.issue_tokens(db, user)
    user.is_active = False
    db.commit()
    assert refresh(client, tokens.refresh_token).status_code == 403
    db.expire_all()
    assert db.query(RefreshToken).filter_by(user_id=user.id, revoked=False).count() == 0


def test_refresh_validation(client: TestClient, db: Session) -> None:
    assert client.post("/api/v1/auth/refresh", json={}).status_code == 422
    assert refresh(client, "").status_code == 422
    assert refresh(client, "x" * 513).status_code == 422


def test_logout_revokes_refresh_token(client: TestClient, db: Session, user: User) -> None:
    tokens = auth_service.issue_tokens(db, user)
    response = client.post("/api/v1/auth/logout", json={"refreshToken": tokens.refresh_token})
    assert response.status_code == 204
    assert refresh(client, tokens.refresh_token).status_code == 401
    # Idempotent, even for unknown tokens.
    again = client.post("/api/v1/auth/logout", json={"refreshToken": tokens.refresh_token})
    assert again.status_code == 204
    unknown = client.post("/api/v1/auth/logout", json={"refreshToken": "nope"})
    assert unknown.status_code == 204


@pytest.mark.usefixtures("rate_limiting")
def test_refresh_rate_limited(client: TestClient, db: Session) -> None:
    statuses = [refresh(client, f"token-{i}").status_code for i in range(11)]
    assert statuses[:10] == [401] * 10
    assert statuses[10] == 429
    response = refresh(client, "token-x")
    assert response.json() == {"detail": RATE_LIMIT_MESSAGE}
