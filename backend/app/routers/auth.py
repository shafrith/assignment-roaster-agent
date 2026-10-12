"""Authentication endpoints: GitHub OAuth login, token refresh, logout, profile.

OAuth errors on the browser-facing callback never render JSON: the user is redirected to
``{FRONTEND_URL}/login?error=<code>`` with one of ``oauth_denied``, ``invalid_state``,
``github_error`` or ``inactive``. On success the tokens are delivered in the URL *fragment*
(``{FRONTEND_URL}/auth/callback#access=...&refresh=...``) so they never reach server logs.
"""

import logging
from typing import Literal
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.auth.jwt import (
    OAUTH_STATE_TTL,
    create_oauth_state,
    nonces_match,
    verify_oauth_state,
)
from app.config import settings
from app.dependencies import get_current_user, get_db
from app.exceptions import AppError, UnauthorizedError
from app.models.user import User
from app.rate_limit import limiter
from app.schemas.auth import LogoutRequest, RefreshRequest, TokenResponse
from app.schemas.user import UserResponse, UserSettingsUpdate
from app.services import auth_service, github_oauth, submission_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

OAUTH_STATE_COOKIE = "oauth_state"
OAUTH_COOKIE_PATH = "/api/v1/auth/github"
AUTH_RATE_LIMIT = "10/minute"

LoginErrorCode = Literal["oauth_denied", "invalid_state", "github_error", "inactive"]


def _login_error_redirect(code: LoginErrorCode) -> RedirectResponse:
    """Redirect to the frontend login page with a short error code and clear the state cookie."""
    response = RedirectResponse(
        f"{settings.FRONTEND_URL}/login?{urlencode({'error': code})}",
        status_code=status.HTTP_302_FOUND,
    )
    _clear_state_cookie(response)
    return response


def _clear_state_cookie(response: Response) -> None:
    """Delete the OAuth state cookie."""
    response.delete_cookie(
        OAUTH_STATE_COOKIE,
        path=OAUTH_COOKIE_PATH,
        secure=settings.is_production,
        httponly=True,
        samesite="lax",
    )


@router.get(
    "/github/login",
    status_code=status.HTTP_302_FOUND,
    response_class=RedirectResponse,
    summary="Start GitHub OAuth login",
)
@limiter.limit(AUTH_RATE_LIMIT)
async def github_login(request: Request) -> RedirectResponse:
    """Redirect the browser to GitHub's authorize page with a signed ``state``.

    The state's nonce is also set in an httpOnly ``oauth_state`` cookie (double-submit check).
    """
    if not settings.GITHUB_CLIENT_ID or not settings.GITHUB_CLIENT_SECRET:
        logger.error("GitHub OAuth is not configured (GITHUB_CLIENT_ID/SECRET missing)")
        return _login_error_redirect("github_error")

    state, nonce = create_oauth_state()
    response = RedirectResponse(
        github_oauth.build_authorize_url(state), status_code=status.HTTP_302_FOUND
    )
    response.set_cookie(
        OAUTH_STATE_COOKIE,
        nonce,
        max_age=int(OAUTH_STATE_TTL.total_seconds()),
        path=OAUTH_COOKIE_PATH,
        secure=settings.is_production,
        httponly=True,
        samesite="lax",
    )
    return response


@router.get(
    "/github/callback",
    status_code=status.HTTP_302_FOUND,
    response_class=RedirectResponse,
    summary="GitHub OAuth callback",
)
@limiter.limit(AUTH_RATE_LIMIT)
async def github_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Verify state, exchange the code, upsert the user, and hand tokens to the frontend."""
    if error:
        logger.info("GitHub OAuth returned error=%s", error[:64])
        return _login_error_redirect("oauth_denied")

    if not state:
        return _login_error_redirect("invalid_state")
    try:
        nonce = verify_oauth_state(state)
    except UnauthorizedError:
        return _login_error_redirect("invalid_state")
    if not nonces_match(request.cookies.get(OAUTH_STATE_COOKIE), nonce):
        logger.info("OAuth state cookie missing or mismatched")
        return _login_error_redirect("invalid_state")

    if not code:
        return _login_error_redirect("oauth_denied")

    try:
        github_token = await github_oauth.exchange_code(code)
        gh_user = await github_oauth.fetch_github_user(github_token)
        user = auth_service.upsert_user_from_github(db, gh_user)
    except AppError as exc:
        logger.warning("GitHub OAuth callback failed: %s", type(exc).__name__)
        return _login_error_redirect("github_error")

    if not user.is_active:
        logger.info("Inactive user id=%d attempted login", user.id)
        return _login_error_redirect("inactive")

    tokens = auth_service.issue_tokens(db, user)
    fragment = urlencode({"access": tokens.access_token, "refresh": tokens.refresh_token})
    response = RedirectResponse(
        f"{settings.FRONTEND_URL}/auth/callback#{fragment}", status_code=status.HTTP_302_FOUND
    )
    _clear_state_cookie(response)
    return response


@router.post("/refresh", response_model=TokenResponse, summary="Rotate refresh token")
@limiter.limit(AUTH_RATE_LIMIT)
async def refresh(
    request: Request, body: RefreshRequest, db: Session = Depends(get_db)
) -> TokenResponse:
    """Exchange a valid refresh token for a new token pair (the old one is revoked)."""
    return auth_service.rotate_refresh_token(db, body.refresh_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, summary="Revoke refresh token")
async def logout(body: LogoutRequest, db: Session = Depends(get_db)) -> Response:
    """Revoke the given refresh token. Always 204 (idempotent).

    Known MVP limitation (SEC-9): access JWTs are stateless, so an already-issued access token
    stays valid until it expires (``ACCESS_TOKEN_EXPIRE_MINUTES``, 30 min) after logout. The
    client must discard it; deactivated users are still blocked on every request.
    """
    auth_service.revoke_refresh_token(db, body.refresh_token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _user_response(db: Session, user: User) -> UserResponse:
    """Build the profile response including the user's daily quota usage."""
    response = UserResponse.model_validate(user)
    response.daily_limit = settings.ROAST_DAILY_LIMIT
    response.roasts_used_today = submission_service.attempts_used_today(db, user.id)
    return response


@router.get("/me", response_model=UserResponse, summary="Current user profile")
async def get_me(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> UserResponse:
    """Return the authenticated user's profile (no email)."""
    return _user_response(db, current_user)


@router.patch("/me", response_model=UserResponse, summary="Update account settings")
async def update_me(
    body: UserSettingsUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserResponse:
    """Update the authenticated user's settings (``defaultRoastPublic``)."""
    user = auth_service.update_settings(db, current_user, body.default_roast_public)
    return _user_response(db, user)
