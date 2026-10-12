"""GitHub OAuth web flow: authorize URL, code exchange, and user profile lookup.

Only the ``read:user user:email`` scopes are requested (never ``repo``). Tokens are never logged.
"""

import logging
from typing import Any
from urllib.parse import urlencode

import httpx

from app.config import settings
from app.exceptions import UnauthorizedError, UpstreamError

logger = logging.getLogger(__name__)

GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_API_BASE = "https://api.github.com"
OAUTH_SCOPE = "read:user user:email"
HTTP_TIMEOUT_SECONDS = 10.0

GITHUB_DOWN_MESSAGE = "GitHub konjam mood-la illa, apram try pannu! 🐙"
BAD_CODE_MESSAGE = "GitHub login code sariyilla, thirumba login pannu da!"

GitHubUser = dict[str, Any]


def build_authorize_url(state: str) -> str:
    """Build the GitHub authorize URL the browser is redirected to.

    Args:
        state: Signed OAuth state value (see :func:`app.auth.jwt.create_oauth_state`).

    Returns:
        The full ``https://github.com/login/oauth/authorize?...`` URL.
    """
    params = {
        "client_id": settings.GITHUB_CLIENT_ID,
        "redirect_uri": settings.GITHUB_REDIRECT_URI,
        "scope": OAUTH_SCOPE,
        "state": state,
        "allow_signup": "true",
    }
    return f"{GITHUB_AUTHORIZE_URL}?{urlencode(params)}"


def _client() -> httpx.AsyncClient:
    """Return an HTTP client with the standard timeout."""
    return httpx.AsyncClient(timeout=HTTP_TIMEOUT_SECONDS)


async def exchange_code(code: str) -> str:
    """Exchange an OAuth ``code`` for a GitHub user access token.

    Args:
        code: The ``code`` query parameter from the callback.

    Returns:
        The GitHub access token (kept in memory only; never stored or logged).

    Raises:
        UnauthorizedError: If GitHub rejects the code.
        UpstreamError: If GitHub is unreachable or returns an unexpected response.
    """
    payload = {
        "client_id": settings.GITHUB_CLIENT_ID,
        "client_secret": settings.GITHUB_CLIENT_SECRET,
        "code": code,
        "redirect_uri": settings.GITHUB_REDIRECT_URI,
    }
    try:
        async with _client() as client:
            response = await client.post(
                GITHUB_TOKEN_URL, data=payload, headers={"Accept": "application/json"}
            )
    except httpx.HTTPError as exc:
        logger.warning("GitHub token exchange request failed: %s", type(exc).__name__)
        raise UpstreamError(GITHUB_DOWN_MESSAGE) from exc

    if response.status_code != 200:
        logger.warning("GitHub token exchange returned HTTP %d", response.status_code)
        raise UpstreamError(GITHUB_DOWN_MESSAGE)
    try:
        data = response.json()
    except ValueError as exc:
        raise UpstreamError(GITHUB_DOWN_MESSAGE) from exc

    # GitHub reports OAuth errors (e.g. bad_verification_code) with HTTP 200 + an "error" field.
    if not isinstance(data, dict) or "error" in data:
        error_code = data.get("error") if isinstance(data, dict) else "invalid_body"
        logger.info("GitHub token exchange rejected: %s", error_code)
        raise UnauthorizedError(BAD_CODE_MESSAGE)
    token = data.get("access_token")
    if not isinstance(token, str) or not token:
        raise UpstreamError(GITHUB_DOWN_MESSAGE)
    return token


async def _get_json(client: httpx.AsyncClient, path: str, token: str) -> Any:
    """GET ``api.github.com{path}`` with the user token and return the parsed JSON body."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    try:
        response = await client.get(f"{GITHUB_API_BASE}{path}", headers=headers)
    except httpx.HTTPError as exc:
        logger.warning("GitHub API %s request failed: %s", path, type(exc).__name__)
        raise UpstreamError(GITHUB_DOWN_MESSAGE) from exc
    if response.status_code == 401:
        raise UnauthorizedError(BAD_CODE_MESSAGE)
    if response.status_code != 200:
        logger.warning("GitHub API %s returned HTTP %d", path, response.status_code)
        raise UpstreamError(GITHUB_DOWN_MESSAGE)
    try:
        return response.json()
    except ValueError as exc:
        raise UpstreamError(GITHUB_DOWN_MESSAGE) from exc


def _primary_verified_email(emails: Any) -> str | None:
    """Pick the primary verified address from a ``/user/emails`` response."""
    if not isinstance(emails, list):
        return None
    for entry in emails:
        if (
            isinstance(entry, dict)
            and entry.get("primary")
            and entry.get("verified")
            and isinstance(entry.get("email"), str)
        ):
            return str(entry["email"])
    return None


async def fetch_github_user(token: str) -> GitHubUser:
    """Fetch the authenticated GitHub user's profile.

    If the public profile has no email, the primary verified address from ``/user/emails`` is
    used (best effort; failures there are ignored).

    Args:
        token: GitHub user access token from :func:`exchange_code`.

    Returns:
        The ``/user`` payload (``id``, ``login``, ``name``, ``avatar_url``, ``email``, ...).

    Raises:
        UnauthorizedError: If the token is rejected.
        UpstreamError: If GitHub fails or returns an unexpected payload.
    """
    async with _client() as client:
        user = await _get_json(client, "/user", token)
        if (
            not isinstance(user, dict)
            or not isinstance(user.get("id"), int)
            or not isinstance(user.get("login"), str)
        ):
            raise UpstreamError(GITHUB_DOWN_MESSAGE)
        if not user.get("email"):
            try:
                emails = await _get_json(client, "/user/emails", token)
            except (UnauthorizedError, UpstreamError):
                emails = None
            user["email"] = _primary_verified_email(emails)
    return user
