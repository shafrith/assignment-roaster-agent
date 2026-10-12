"""JWT access tokens, opaque refresh tokens, and signed OAuth ``state`` values.

Authentication is GitHub-only: there are no passwords anywhere in the system.
"""

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

import jwt
from jwt import InvalidTokenError

from app.config import settings
from app.exceptions import UnauthorizedError

# Pinned on purpose (never read from the environment): accepting a configurable algorithm
# invites algorithm-confusion attacks with the HMAC secret.
JWT_ALGORITHM = "HS256"
# Claims every token we issue carries; PyJWT rejects tokens missing any of them.
_REQUIRED_CLAIMS = ["exp", "iat", "type"]

ACCESS_TOKEN_TYPE = "access"
OAUTH_STATE_TYPE = "oauth_state"
OAUTH_STATE_TTL = timedelta(minutes=10)
REFRESH_TOKEN_BYTES = 48

INVALID_TOKEN_MESSAGE = "Token sariyilla machan, thirumba login pannu! 🔑"
INVALID_STATE_MESSAGE = "Login state sariyilla, thirumba try pannu da!"


def _encode(claims: dict[str, object]) -> str:
    """Sign ``claims`` with the application secret."""
    return jwt.encode(claims, settings.SECRET_KEY, algorithm=JWT_ALGORITHM)


def _decode(token: str) -> dict[str, object]:
    """Verify signature/expiry of ``token`` and return its claims.

    Raises:
        InvalidTokenError: If the token is malformed, tampered with, expired, signed with a
            different algorithm, or missing a required claim.
    """
    claims: dict[str, object] = jwt.decode(
        token,
        settings.SECRET_KEY,
        algorithms=[JWT_ALGORITHM],
        options={"require": _REQUIRED_CLAIMS},
    )
    return claims


def create_access_token(user_id: int) -> str:
    """Create a short-lived access JWT for ``user_id``.

    Args:
        user_id: Primary key of the authenticated user.

    Returns:
        The encoded JWT with ``sub``, ``type="access"``, ``iat`` and ``exp`` claims.
    """
    now = datetime.now(UTC)
    return _encode(
        {
            "sub": str(user_id),
            "type": ACCESS_TOKEN_TYPE,
            "iat": now,
            "exp": now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        }
    )


def decode_access_token(token: str) -> int:
    """Validate an access JWT and return the user id it was issued for.

    Args:
        token: Encoded access token from the ``Authorization`` header.

    Returns:
        The user id from the ``sub`` claim.

    Raises:
        UnauthorizedError: If the token is invalid, expired, or not an access token.
    """
    try:
        claims = _decode(token)
    except InvalidTokenError as exc:
        raise UnauthorizedError(INVALID_TOKEN_MESSAGE) from exc
    if claims.get("type") != ACCESS_TOKEN_TYPE:
        raise UnauthorizedError(INVALID_TOKEN_MESSAGE)
    subject = claims.get("sub")
    if not isinstance(subject, str) or not subject.isdigit():
        raise UnauthorizedError(INVALID_TOKEN_MESSAGE)
    return int(subject)


def hash_token(raw_token: str) -> str:
    """Return the hex SHA-256 digest of a raw refresh token (what the DB stores)."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def create_refresh_token() -> tuple[str, str]:
    """Generate a new opaque refresh token.

    Returns:
        ``(raw_token, token_hash)``: the raw value goes to the client, only the hash is stored.
    """
    raw_token = secrets.token_urlsafe(REFRESH_TOKEN_BYTES)
    return raw_token, hash_token(raw_token)


def create_oauth_state() -> tuple[str, str]:
    """Create a signed, short-lived OAuth ``state`` value bound to a random nonce.

    The nonce is also set in an httpOnly cookie on the login redirect; the callback requires
    the cookie to match the nonce inside the state (double-submit CSRF protection).

    Returns:
        ``(state_jwt, nonce)``.
    """
    nonce = secrets.token_urlsafe(32)
    now = datetime.now(UTC)
    state = _encode(
        {"type": OAUTH_STATE_TYPE, "nonce": nonce, "iat": now, "exp": now + OAUTH_STATE_TTL}
    )
    return state, nonce


def verify_oauth_state(state: str) -> str:
    """Validate an OAuth ``state`` value and return its nonce.

    Args:
        state: The ``state`` query parameter GitHub echoed back to the callback.

    Returns:
        The nonce embedded in the state.

    Raises:
        UnauthorizedError: If the state is invalid, expired, or of the wrong type.
    """
    try:
        claims = _decode(state)
    except InvalidTokenError as exc:
        raise UnauthorizedError(INVALID_STATE_MESSAGE) from exc
    nonce = claims.get("nonce")
    if claims.get("type") != OAUTH_STATE_TYPE or not isinstance(nonce, str) or not nonce:
        raise UnauthorizedError(INVALID_STATE_MESSAGE)
    return nonce


def nonces_match(expected: str | None, actual: str) -> bool:
    """Constant-time comparison of the cookie nonce against the state nonce."""
    if not expected:
        return False
    return secrets.compare_digest(expected.encode("utf-8"), actual.encode("utf-8"))
