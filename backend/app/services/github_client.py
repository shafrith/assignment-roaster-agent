"""Async read-only client for the public GitHub REST API.

Security: the base URL is hard-coded to ``https://api.github.com`` and every path segment is
URL-quoted, so user input can never redirect requests to another host. Redirects are followed
manually and only when they stay on ``api.github.com`` (GitHub uses them for renamed repos).
"""

import logging
import re
from datetime import datetime
from types import TracebackType
from typing import Any, Self
from urllib.parse import quote, urlsplit

import httpx

from app.config import settings
from app.services.contracts import GitHubUnavailableError, RepoInfo, RepoNotFoundError

logger = logging.getLogger(__name__)

GITHUB_API_BASE = "https://api.github.com"
GITHUB_API_HOST = "api.github.com"
REQUEST_TIMEOUT_SECONDS = 15.0
DEFAULT_MAX_FILE_BYTES = 20_000
MAX_REDIRECTS = 3

EMPTY_REPO_MESSAGE = "Repo-la onnume illa da, empty-a irukku! 🫙"

_LAST_PAGE_RE = re.compile(r"[?&]page=(\d+)[^>]*>;\s*rel=\"last\"")
_REDIRECT_CODES = frozenset({301, 302, 307, 308})


def quote_segment(segment: str) -> str:
    """URL-quote a single path segment (``/`` included) for safe use in an API path."""
    return quote(segment, safe="")


def quote_repo_path(path: str) -> str:
    """URL-quote a repository file path segment by segment.

    Raises:
        ValueError: If the path contains empty, ``.`` or ``..`` segments.
    """
    segments = path.split("/")
    if any(seg in {"", ".", ".."} for seg in segments):
        raise ValueError(f"Unsafe repository path: {path!r}")
    return "/".join(quote_segment(seg) for seg in segments)


def parse_last_page(link_header: str | None) -> int | None:
    """Extract the ``rel="last"`` page number from a GitHub ``Link`` header."""
    if not link_header:
        return None
    match = _LAST_PAGE_RE.search(link_header)
    return int(match.group(1)) if match else None


def parse_github_datetime(value: Any) -> datetime | None:
    """Parse an ISO-8601 timestamp such as ``2024-01-02T03:04:05Z``; ``None`` if invalid."""
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def decode_text(data: bytes, truncated: bool) -> str | None:
    """Decode file bytes as UTF-8 text, or return ``None`` for binary/undecodable content.

    When ``truncated`` is set, a multi-byte character cut at the end is dropped instead of
    failing the decode.
    """
    if b"\x00" in data[:8192]:
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as exc:
        if truncated and exc.start >= len(data) - 3:
            return data[: exc.start].decode("utf-8", errors="strict")
        return None


class GitHubClient:
    """Thin async wrapper over the GitHub REST API. Use as ``async with GitHubClient() as gh``."""

    def __init__(self, token: str | None = None, transport: httpx.AsyncBaseTransport | None = None):
        """Create a client.

        Args:
            token: Optional API token; defaults to ``settings.GITHUB_API_TOKEN``.
            transport: Optional httpx transport (tests only).
        """
        token = settings.GITHUB_API_TOKEN if token is None else token
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "assignment-roaster",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self._client = httpx.AsyncClient(
            base_url=GITHUB_API_BASE,
            headers=headers,
            timeout=REQUEST_TIMEOUT_SECONDS,
            follow_redirects=False,
            transport=transport,
        )

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        """Close the underlying HTTP connection pool."""
        await self._client.aclose()

    # ------------------------------------------------------------------ internals

    @staticmethod
    def _raise_for_unavailable(response: httpx.Response) -> None:
        """Map rate limits and server errors to :class:`GitHubUnavailableError`."""
        status = response.status_code
        if status == 429 or (
            status == 403 and response.headers.get("x-ratelimit-remaining") == "0"
        ):
            logger.warning("GitHub API rate limit hit (status %s)", status)
            raise GitHubUnavailableError()
        if status >= 500:
            logger.warning("GitHub API server error %s", status)
            raise GitHubUnavailableError()

    async def _get(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        accept: str | None = None,
    ) -> httpx.Response:
        """GET ``path`` (relative to the API base), following only same-host redirects."""
        headers = {"Accept": accept} if accept else None
        url: str = path
        for _ in range(MAX_REDIRECTS + 1):
            try:
                response = await self._client.get(url, params=params, headers=headers)
            except httpx.HTTPError as exc:
                logger.warning("GitHub API request failed: %s", type(exc).__name__)
                raise GitHubUnavailableError() from exc
            if response.status_code not in _REDIRECT_CODES:
                self._raise_for_unavailable(response)
                return response
            location = response.headers.get("location", "")
            target = urlsplit(location)
            if target.scheme != "https" or target.netloc.lower() != GITHUB_API_HOST:
                logger.warning("Refusing GitHub redirect to a non-API host")
                raise GitHubUnavailableError()
            url = location
            params = None  # the Location already carries the query string
        raise GitHubUnavailableError()

    async def _get_json(self, path: str, *, params: dict[str, Any] | None = None) -> Any:
        response = await self._get(path, params=params)
        if response.status_code in {404, 451}:
            raise RepoNotFoundError()
        if response.status_code >= 400:
            logger.warning("GitHub API returned %s", response.status_code)
            raise GitHubUnavailableError()
        try:
            return response.json()
        except ValueError as exc:
            raise GitHubUnavailableError() from exc

    @staticmethod
    def _repo_path(owner: str, repo: str) -> str:
        return f"/repos/{quote_segment(owner)}/{quote_segment(repo)}"

    # ------------------------------------------------------------------ public API

    async def get_repo_info(self, owner: str, repo: str) -> RepoInfo:
        """Fetch repo metadata and resolve the HEAD sha of the default branch.

        Raises:
            RepoNotFoundError: Repo missing, private, or empty.
            GitHubUnavailableError: Rate limit, timeout, or GitHub error.
        """
        data = await self._get_json(self._repo_path(owner, repo))
        if not isinstance(data, dict) or data.get("private") or data.get("visibility") == "private":
            raise RepoNotFoundError()
        default_branch = data.get("default_branch")
        if not isinstance(default_branch, str) or not default_branch:
            raise RepoNotFoundError(EMPTY_REPO_MESSAGE)

        canonical_owner = (data.get("owner") or {}).get("login") or owner
        canonical_name = data.get("name") or repo
        branch_path = (
            f"{self._repo_path(canonical_owner, canonical_name)}"
            f"/branches/{quote_segment(default_branch)}"
        )
        try:
            branch = await self._get_json(branch_path)
        except RepoNotFoundError as exc:
            # Empty repositories have a default branch name but no commits.
            raise RepoNotFoundError(EMPTY_REPO_MESSAGE) from exc
        head_sha = ((branch or {}).get("commit") or {}).get("sha")
        if not isinstance(head_sha, str) or not head_sha:
            raise RepoNotFoundError(EMPTY_REPO_MESSAGE)

        return RepoInfo(
            owner=str(canonical_owner),
            name=str(canonical_name),
            default_branch=default_branch,
            head_sha=head_sha,
            size_kb=int(data.get("size") or 0),
            is_private=bool(data.get("private")),
        )

    async def get_languages(self, owner: str, repo: str) -> dict[str, int]:
        """Return GitHub's language byte counts, e.g. ``{"Python": 12034}``."""
        data = await self._get_json(f"{self._repo_path(owner, repo)}/languages")
        if not isinstance(data, dict):
            return {}
        return {str(k): int(v) for k, v in data.items() if isinstance(v, int)}

    async def get_tree(self, owner: str, repo: str, sha: str) -> list[dict[str, Any]]:
        """Return the recursive git tree at ``sha`` (entries with ``path``, ``type``, ``size``).

        GitHub truncates very large trees; the partial listing is returned and a warning logged.
        """
        data = await self._get_json(
            f"{self._repo_path(owner, repo)}/git/trees/{quote_segment(sha)}",
            params={"recursive": "1"},
        )
        if not isinstance(data, dict):
            return []
        if data.get("truncated"):
            logger.warning(
                "GitHub tree for %s/%s truncated; analysing partial listing", owner, repo
            )
        entries = data.get("tree") or []
        return [e for e in entries if isinstance(e, dict) and isinstance(e.get("path"), str)]

    async def get_file_text(
        self,
        owner: str,
        repo: str,
        path: str,
        ref: str,
        max_bytes: int = DEFAULT_MAX_FILE_BYTES,
    ) -> tuple[str, bool] | None:
        """Fetch a file's raw content as text, reading at most ``max_bytes`` bytes.

        Returns:
            ``(text, truncated)``, or ``None`` if the file is missing, binary, or undecodable.
            The text is NOT secret-redacted; callers must run it through the secret scanner.
        """
        try:
            api_path = f"{self._repo_path(owner, repo)}/contents/{quote_repo_path(path)}"
        except ValueError:
            return None
        request = self._client.build_request(
            "GET",
            api_path,
            params={"ref": ref},
            headers={"Accept": "application/vnd.github.raw"},
        )
        try:
            response = await self._client.send(request, stream=True)
        except httpx.HTTPError as exc:
            logger.warning("GitHub file fetch failed: %s", type(exc).__name__)
            raise GitHubUnavailableError() from exc
        try:
            self._raise_for_unavailable(response)
            if response.status_code != 200:
                return None
            chunks: list[bytes] = []
            received = 0
            truncated = False
            async for chunk in response.aiter_bytes():
                remaining = max_bytes - received
                if len(chunk) > remaining:
                    chunks.append(chunk[:remaining])
                    truncated = True
                    break
                chunks.append(chunk)
                received += len(chunk)
        except httpx.HTTPError as exc:
            logger.warning("GitHub file stream failed: %s", type(exc).__name__)
            raise GitHubUnavailableError() from exc
        finally:
            await response.aclose()

        text = decode_text(b"".join(chunks), truncated)
        return None if text is None else (text, truncated)

    async def get_commit_stats(
        self, owner: str, repo: str, sha: str
    ) -> tuple[int, datetime | None]:
        """Return ``(commit_count, last_commit_at)`` for history reachable from ``sha``.

        Uses ``per_page=1`` so the ``Link`` header's last page number equals the commit count.
        """
        response = await self._get(
            f"{self._repo_path(owner, repo)}/commits", params={"sha": sha, "per_page": "1"}
        )
        if response.status_code in {404, 409}:  # 409: empty repository
            return 0, None
        if response.status_code >= 400:
            raise GitHubUnavailableError()
        try:
            commits = response.json()
        except ValueError as exc:
            raise GitHubUnavailableError() from exc
        if not isinstance(commits, list) or not commits:
            return 0, None

        count = parse_last_page(response.headers.get("link")) or len(commits)
        commit = commits[0].get("commit") or {}
        last = parse_github_datetime((commit.get("committer") or {}).get("date")) or (
            parse_github_datetime((commit.get("author") or {}).get("date"))
        )
        return count, last
