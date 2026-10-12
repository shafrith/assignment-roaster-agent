"""Authentication business logic: user upsert, token issuance, rotation, and revocation."""

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.jwt import create_access_token, create_refresh_token, hash_token
from app.config import settings
from app.exceptions import ForbiddenError, UnauthorizedError, UpstreamError
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.schemas.auth import TokenResponse
from app.services.github_oauth import GitHubUser

logger = logging.getLogger(__name__)

INACTIVE_USER_MESSAGE = "Un account-a block pannirukkanga machan. Admin-a contact pannu."
INVALID_REFRESH_MESSAGE = "Session mudinjuchu machan, thirumba login pannu! 🔑"
TOKEN_REUSE_MESSAGE = "Edho thappa irukku! Ella session-um logout pannittom, thirumba login pannu."
CONCURRENT_REFRESH_MESSAGE = "Vera tab already session-a refresh pannidichu, thirumba try pannu 🔁"

# A just-rotated token presented again within this window, while its replacement is still
# unused, is treated as a concurrent refresh from another tab rather than theft (COR-5).
REFRESH_REUSE_GRACE = timedelta(seconds=30)

_USERNAME_MAX = 100
_DISPLAY_NAME_MAX = 200
_AVATAR_MAX = 500
_EMAIL_MAX = 255


def _clip(value: object, limit: int) -> str | None:
    """Return ``value`` as a string clipped to ``limit`` chars, or None if empty/non-string."""
    if not isinstance(value, str) or not value:
        return None
    return value[:limit]


def ensure_active(user: User) -> None:
    """Raise 403 if ``user`` has been deactivated."""
    if not user.is_active:
        raise ForbiddenError(INACTIVE_USER_MESSAGE)


def _apply_github_profile(user: User, gh_user: GitHubUser) -> None:
    """Copy mutable GitHub profile fields onto ``user``."""
    user.github_username = str(gh_user["login"])[:_USERNAME_MAX]
    user.display_name = _clip(gh_user.get("name"), _DISPLAY_NAME_MAX)
    user.avatar_url = _clip(gh_user.get("avatar_url"), _AVATAR_MAX)
    user.email = _clip(gh_user.get("email"), _EMAIL_MAX)


def upsert_user_from_github(db: Session, gh_user: GitHubUser) -> User:
    """Create or update the user identified by the GitHub account id.

    Username, display name, avatar and email are refreshed on every login.

    Args:
        db: Database session.
        gh_user: Payload from :func:`app.services.github_oauth.fetch_github_user`.

    Returns:
        The persisted user.

    Raises:
        UpstreamError: If the payload lacks a numeric ``id`` or a ``login``.
    """
    github_id = gh_user.get("id")
    login = gh_user.get("login")
    if not isinstance(github_id, int) or not isinstance(login, str) or not login:
        raise UpstreamError("GitHub profile vinoda-ma irukku, apram try pannu!")

    user = db.scalar(select(User).where(User.github_id == github_id))
    if user is None:
        user = User(github_id=github_id)
        _apply_github_profile(user, gh_user)
        db.add(user)
        try:
            db.commit()
        except IntegrityError:
            # Concurrent first login for the same GitHub account: fall back to the winner's row.
            db.rollback()
            user = db.scalar(select(User).where(User.github_id == github_id))
            if user is None:
                raise
            _apply_github_profile(user, gh_user)
            db.commit()
        else:
            logger.info("Created user id=%d for github_id=%d", user.id, github_id)
    else:
        _apply_github_profile(user, gh_user)
        db.commit()
    db.refresh(user)
    return user


def _add_refresh_token(db: Session, user: User) -> tuple[str, RefreshToken]:
    """Create (but do not commit) a refresh token row; return the raw token and the row."""
    raw_refresh, refresh_hash = create_refresh_token()
    row = RefreshToken(
        user_id=user.id,
        token_hash=refresh_hash,
        expires_at=datetime.now(UTC) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )
    db.add(row)
    return raw_refresh, row


def issue_tokens(db: Session, user: User) -> TokenResponse:
    """Issue a new access token and a new (stored-hashed) refresh token for ``user``.

    Args:
        db: Database session.
        user: The authenticated, active user.

    Returns:
        The token pair; only the refresh token's SHA-256 hash is persisted.
    """
    raw_refresh, _row = _add_refresh_token(db, user)
    db.commit()
    return TokenResponse(access_token=create_access_token(user.id), refresh_token=raw_refresh)


def _revoke_all_for_user(db: Session, user_id: int) -> None:
    """Revoke every still-active refresh token belonging to ``user_id``."""
    db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked.is_(False))
        .values(revoked=True, revoked_at=datetime.now(UTC))
    )


def _is_concurrent_refresh(db: Session, stored: RefreshToken, now: datetime) -> bool:
    """True when ``stored`` was rotated moments ago and its replacement is still unused.

    That is what two tabs refreshing with the same token at once look like; a thief replaying
    an old token, or a replacement that was already rotated or revoked, is not covered.
    """
    if stored.revoked_at is None or stored.replaced_by_id is None:
        return False
    if now - stored.revoked_at > REFRESH_REUSE_GRACE:
        return False
    replacement = db.get(RefreshToken, stored.replaced_by_id)
    return replacement is not None and not replacement.revoked


def rotate_refresh_token(db: Session, raw_token: str) -> TokenResponse:
    """Validate a refresh token, revoke it, and issue a fresh token pair.

    Presenting an already-revoked token is treated as theft: every refresh token of that user
    is revoked and the request is rejected. Exception: within :data:`REFRESH_REUSE_GRACE` of a
    rotation whose replacement is still unused (another tab refreshed concurrently), the
    request is rejected with 401 but no session is revoked.

    Args:
        db: Database session.
        raw_token: The refresh token sent by the client.

    Returns:
        The new token pair.

    Raises:
        UnauthorizedError: If the token is unknown, expired, or revoked (reuse).
        ForbiddenError: If the user is inactive.
    """
    stored = db.scalar(
        select(RefreshToken)
        .where(RefreshToken.token_hash == hash_token(raw_token))
        .with_for_update()
    )
    if stored is None:
        raise UnauthorizedError(INVALID_REFRESH_MESSAGE)

    now = datetime.now(UTC)
    if stored.revoked:
        if _is_concurrent_refresh(db, stored, now):
            db.rollback()
            logger.info("Concurrent refresh for user_id=%d within grace window", stored.user_id)
            raise UnauthorizedError(CONCURRENT_REFRESH_MESSAGE)
        logger.warning("Refresh token reuse detected for user_id=%d; revoking all", stored.user_id)
        _revoke_all_for_user(db, stored.user_id)
        db.commit()
        raise UnauthorizedError(TOKEN_REUSE_MESSAGE)

    if stored.expires_at <= now:
        stored.revoked = True
        stored.revoked_at = now
        db.commit()
        raise UnauthorizedError(INVALID_REFRESH_MESSAGE)

    user = stored.user
    if not user.is_active:
        _revoke_all_for_user(db, user.id)
        db.commit()
        ensure_active(user)

    raw_refresh, replacement = _add_refresh_token(db, user)
    db.flush()
    stored.revoked = True
    stored.revoked_at = now
    stored.replaced_by_id = replacement.id
    db.commit()
    return TokenResponse(access_token=create_access_token(user.id), refresh_token=raw_refresh)


def revoke_refresh_token(db: Session, raw_token: str) -> None:
    """Revoke a refresh token (logout). Unknown or already-revoked tokens are ignored.

    Args:
        db: Database session.
        raw_token: The refresh token sent by the client.
    """
    db.execute(
        update(RefreshToken)
        .where(RefreshToken.token_hash == hash_token(raw_token), RefreshToken.revoked.is_(False))
        .values(revoked=True, revoked_at=datetime.now(UTC))
    )
    db.commit()


def update_settings(db: Session, user: User, default_roast_public: bool) -> User:
    """Update the user's account settings.

    Args:
        db: Database session.
        user: The authenticated user.
        default_roast_public: Whether new roasts are public by default.

    Returns:
        The refreshed user.
    """
    user.default_roast_public = default_roast_public
    db.commit()
    db.refresh(user)
    return user
