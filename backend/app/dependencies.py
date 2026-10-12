"""Shared FastAPI dependencies."""

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.auth.jwt import INVALID_TOKEN_MESSAGE, decode_access_token
from app.database import get_db
from app.exceptions import AppError, UnauthorizedError
from app.models.user import User
from app.services.auth_service import ensure_active

__all__ = ["get_current_user", "get_current_user_optional", "get_db"]

bearer_scheme = HTTPBearer(auto_error=False)

NOT_AUTHENTICATED_MESSAGE = "Login pannu machan, apram dhaan idhu! 🔐"


def _resolve_user(token: str, db: Session) -> User:
    """Decode an access token and load its active user.

    Raises:
        UnauthorizedError: If the token is invalid or the user no longer exists.
        ForbiddenError: If the user is inactive.
    """
    user_id = decode_access_token(token)
    user = db.get(User, user_id)
    if user is None:
        raise UnauthorizedError(INVALID_TOKEN_MESSAGE)
    ensure_active(user)
    return user


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Return the authenticated user from the ``Authorization: Bearer <access>`` header.

    Raises:
        UnauthorizedError: 401 if the header is missing, the token is invalid/expired, or the
            user does not exist.
        ForbiddenError: 403 if the user is inactive.
    """
    if credentials is None or not credentials.credentials:
        raise UnauthorizedError(NOT_AUTHENTICATED_MESSAGE)
    return _resolve_user(credentials.credentials, db)


async def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User | None:
    """Return the authenticated user, or None for anonymous callers.

    For public endpoints: a missing, invalid, or expired token, or an inactive user, yields
    None instead of an error.
    """
    if credentials is None or not credentials.credentials:
        return None
    try:
        return _resolve_user(credentials.credentials, db)
    except AppError:
        return None
