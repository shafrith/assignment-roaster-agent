"""Validation and normalization of user-submitted GitHub repository URLs.

Only ``https://github.com/{owner}/{repo}`` style URLs are accepted. The parsed ``owner`` and
``repo`` are the ONLY values ever used to build GitHub API requests, so this module is the SSRF
boundary of the roaster: anything that is not unambiguously a public github.com repo is rejected.
"""

import re
from urllib.parse import urlsplit

from app.exceptions import BadRequestError

INVALID_URL_MESSAGE = "Dei, idhu GitHub repo URL-ae illa da! 😅"

MAX_URL_LENGTH = 500
ALLOWED_HOSTS = frozenset({"github.com", "www.github.com"})

# GitHub usernames: 1-39 alphanumerics or single hyphens, no leading/trailing hyphen.
_OWNER_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?$")
_REPO_RE = re.compile(r"^[A-Za-z0-9._-]{1,100}$")

# First path segments on github.com that are site pages, not user/org names.
RESERVED_OWNERS = frozenset(
    {
        "about",
        "account",
        "apps",
        "blog",
        "collections",
        "contact",
        "customer-stories",
        "dashboard",
        "enterprise",
        "events",
        "explore",
        "features",
        "issues",
        "join",
        "login",
        "logout",
        "marketplace",
        "new",
        "notifications",
        "orgs",
        "organizations",
        "pricing",
        "pulls",
        "search",
        "security",
        "settings",
        "site",
        "sponsors",
        "topics",
        "trending",
        "users",
    }
)


def _invalid() -> BadRequestError:
    return BadRequestError(INVALID_URL_MESSAGE)


def parse_github_url(url: str) -> tuple[str, str]:
    """Parse a public GitHub repository URL into ``(owner, repo)``.

    Accepts ``http(s)://(www.)github.com/{owner}/{repo}`` with an optional ``.git`` suffix,
    trailing slash, extra path (``/tree/main/src``), query string, or fragment.

    Args:
        url: Raw URL submitted by the user.

    Returns:
        The ``(owner, repo)`` pair, with ``.git`` stripped and original casing kept.

    Raises:
        BadRequestError: If the URL is not a GitHub repository URL.
    """
    if not isinstance(url, str):
        raise _invalid()
    url = url.strip()
    if not url or len(url) > MAX_URL_LENGTH or any(ch.isspace() for ch in url) or "\\" in url:
        raise _invalid()

    try:
        parts = urlsplit(url)
    except ValueError as exc:
        raise _invalid() from exc

    if parts.scheme.lower() not in {"http", "https"}:
        raise _invalid()
    # ``netloc`` must be exactly the host: this rejects userinfo (``user@``) and ports.
    if parts.netloc.lower() not in ALLOWED_HOSTS:
        raise _invalid()

    segments = [seg for seg in parts.path.split("/") if seg]
    if len(segments) < 2:
        raise _invalid()

    owner, repo = segments[0], segments[1]
    if repo.lower().endswith(".git"):
        repo = repo[: -len(".git")]

    if not _OWNER_RE.fullmatch(owner) or owner.lower() in RESERVED_OWNERS:
        raise _invalid()
    if not _REPO_RE.fullmatch(repo) or repo in {".", ".."}:
        raise _invalid()
    return owner, repo


def normalize_github_url(owner: str, repo: str) -> str:
    """Build the canonical repo URL stored on a submission.

    Args:
        owner: Repository owner from :func:`parse_github_url`.
        repo: Repository name from :func:`parse_github_url`.

    Returns:
        ``https://github.com/{owner}/{repo}``.
    """
    return f"https://github.com/{owner}/{repo}"
