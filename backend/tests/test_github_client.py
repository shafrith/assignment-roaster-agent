"""GitHub REST client: error mapping, redirects, file fetching."""

from collections.abc import AsyncIterator, Iterator

import httpx
import pytest
import respx

from app.services.contracts import GitHubUnavailableError, RepoNotFoundError
from app.services.github_client import (
    EMPTY_REPO_MESSAGE,
    GitHubClient,
    decode_text,
    parse_github_datetime,
    parse_last_page,
    quote_repo_path,
)

HOST = "api.github.com"
REPO = "/repos/octo/repo"
SHA = "c" * 40


@pytest.fixture
def router() -> Iterator[respx.MockRouter]:
    with respx.mock(assert_all_called=False) as mock_router:
        yield mock_router


@pytest.fixture
async def gh() -> AsyncIterator[GitHubClient]:
    async with GitHubClient(token="server-token") as client:
        yield client


def repo_json(**overrides: object) -> dict[str, object]:
    data: dict[str, object] = {
        "name": "repo",
        "owner": {"login": "octo"},
        "default_branch": "main",
        "size": 12,
        "private": False,
    }
    data.update(overrides)
    return data


def route(router: respx.MockRouter, path: str) -> respx.Route:
    return router.get(host=HOST, path=path)


# ---------------------------------------------------------------------------- pure helpers


def test_parse_last_page() -> None:
    link = (
        '<https://api.github.com/repositories/1/commits?per_page=1&page=2>; rel="next", '
        '<https://api.github.com/repositories/1/commits?per_page=1&page=57>; rel="last"'
    )
    assert parse_last_page(link) == 57
    assert parse_last_page(None) is None
    assert parse_last_page('<https://x?page=2>; rel="next"') is None


@pytest.mark.parametrize("value", [None, "", 12, "not a date"])
def test_parse_github_datetime_invalid(value: object) -> None:
    assert parse_github_datetime(value) is None


def test_parse_github_datetime_valid() -> None:
    parsed = parse_github_datetime("2026-09-28T10:15:00Z")
    assert parsed is not None and parsed.tzinfo is not None


def test_quote_repo_path() -> None:
    assert quote_repo_path("src/my file.py") == "src/my%20file.py"
    assert quote_repo_path("a/b?c#d") == "a/b%3Fc%23d"
    for bad in ("../etc/passwd", "a//b", "a/./b", "/abs"):
        with pytest.raises(ValueError):
            quote_repo_path(bad)


def test_decode_text() -> None:
    assert decode_text(b"hello", False) == "hello"
    assert decode_text(b"\x00\x01binary", False) is None
    assert decode_text(b"\xff\xfe bad", False) is None
    cut = "café".encode()[:-1]  # multi-byte char cut by truncation
    assert decode_text(cut, True) == "caf"
    assert decode_text(cut, False) is None


def test_auth_header_only_with_token() -> None:
    with_token = GitHubClient(token="abc")
    without = GitHubClient(token="")
    assert with_token._client.headers["Authorization"] == "Bearer abc"
    assert "Authorization" not in without._client.headers


# ---------------------------------------------------------------------------- repo info


async def test_get_repo_info_success(router: respx.MockRouter, gh: GitHubClient) -> None:
    route(router, REPO).respond(200, json=repo_json(name="Repo", owner={"login": "Octo"}))
    route(router, "/repos/Octo/Repo/branches/main").respond(200, json={"commit": {"sha": SHA}})
    info = await gh.get_repo_info("octo", "repo")
    assert (info.owner, info.name, info.head_sha, info.size_kb) == ("Octo", "Repo", SHA, 12)
    assert info.default_branch == "main"
    assert not info.is_private


@pytest.mark.parametrize("status", [404, 451])
async def test_missing_repo(router: respx.MockRouter, gh: GitHubClient, status: int) -> None:
    route(router, REPO).respond(status, json={"message": "Not Found"})
    with pytest.raises(RepoNotFoundError):
        await gh.get_repo_info("octo", "repo")


@pytest.mark.parametrize(
    "payload", [repo_json(private=True), repo_json(visibility="private"), ["not", "a", "dict"]]
)
async def test_private_repo(router: respx.MockRouter, gh: GitHubClient, payload: object) -> None:
    route(router, REPO).respond(200, json=payload)
    with pytest.raises(RepoNotFoundError):
        await gh.get_repo_info("octo", "repo")


async def test_empty_repo_without_default_branch(
    router: respx.MockRouter, gh: GitHubClient
) -> None:
    route(router, REPO).respond(200, json=repo_json(default_branch=None))
    with pytest.raises(RepoNotFoundError) as exc_info:
        await gh.get_repo_info("octo", "repo")
    assert exc_info.value.detail == EMPTY_REPO_MESSAGE


@pytest.mark.parametrize(
    "branch_response",
    [httpx.Response(404, json={}), httpx.Response(200, json={"commit": {}})],
)
async def test_empty_repo_without_commits(
    router: respx.MockRouter, gh: GitHubClient, branch_response: httpx.Response
) -> None:
    route(router, REPO).respond(200, json=repo_json())
    route(router, f"{REPO}/branches/main").mock(return_value=branch_response)
    with pytest.raises(RepoNotFoundError) as exc_info:
        await gh.get_repo_info("octo", "repo")
    assert exc_info.value.detail == EMPTY_REPO_MESSAGE


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(403, headers={"x-ratelimit-remaining": "0"}, json={}),
        httpx.Response(403, json={"message": "Forbidden"}),
        httpx.Response(429, json={}),
        httpx.Response(500, json={}),
        httpx.Response(502, text="bad gateway"),
        httpx.Response(503, json={}),
        httpx.Response(401, json={}),
        httpx.Response(200, text="<html>not json</html>"),
    ],
)
async def test_unavailable_errors(
    router: respx.MockRouter, gh: GitHubClient, response: httpx.Response
) -> None:
    route(router, REPO).mock(return_value=response)
    with pytest.raises(GitHubUnavailableError):
        await gh.get_repo_info("octo", "repo")


@pytest.mark.parametrize("exc", [httpx.ReadTimeout("slow"), httpx.ConnectError("down")])
async def test_network_errors(router: respx.MockRouter, gh: GitHubClient, exc: Exception) -> None:
    route(router, REPO).mock(side_effect=exc)
    with pytest.raises(GitHubUnavailableError):
        await gh.get_repo_info("octo", "repo")


async def test_same_host_redirect_followed(router: respx.MockRouter, gh: GitHubClient) -> None:
    route(router, REPO).respond(301, headers={"Location": "https://api.github.com/repositories/42"})
    route(router, "/repositories/42").respond(200, json=repo_json(name="renamed"))
    route(router, "/repos/octo/renamed/branches/main").respond(200, json={"commit": {"sha": SHA}})
    info = await gh.get_repo_info("octo", "repo")
    assert info.name == "renamed"


@pytest.mark.parametrize(
    "location",
    [
        "https://evil.example.com/repos/octo/repo",
        "http://api.github.com/repos/octo/repo",
        "https://api.github.com.evil.com/x",
        "/relative/path",
        "",
    ],
)
async def test_cross_host_redirect_rejected(
    router: respx.MockRouter, gh: GitHubClient, location: str
) -> None:
    route(router, REPO).respond(302, headers={"Location": location})
    evil = router.get(host="evil.example.com").respond(200, json=repo_json())
    with pytest.raises(GitHubUnavailableError):
        await gh.get_repo_info("octo", "repo")
    assert not evil.called


async def test_redirect_loop_rejected(router: respx.MockRouter, gh: GitHubClient) -> None:
    route(router, REPO).respond(307, headers={"Location": f"https://{HOST}{REPO}"})
    with pytest.raises(GitHubUnavailableError):
        await gh.get_repo_info("octo", "repo")


async def test_path_segments_are_quoted(router: respx.MockRouter, gh: GitHubClient) -> None:
    captured: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request.url.raw_path.decode())
        return httpx.Response(404)

    router.route(host=HOST).mock(side_effect=handler)
    with pytest.raises(RepoNotFoundError):
        await gh.get_repo_info("a/../../x", "r?y")
    assert captured == ["/repos/a%2F..%2F..%2Fx/r%3Fy"]


# ---------------------------------------------------------------------------- other endpoints


async def test_get_languages(router: respx.MockRouter, gh: GitHubClient) -> None:
    route(router, f"{REPO}/languages").respond(200, json={"Python": 10, "Weird": "x"})
    assert await gh.get_languages("octo", "repo") == {"Python": 10}


async def test_get_languages_non_dict(router: respx.MockRouter, gh: GitHubClient) -> None:
    route(router, f"{REPO}/languages").respond(200, json=[])
    assert await gh.get_languages("octo", "repo") == {}


async def test_get_tree_truncated(router: respx.MockRouter, gh: GitHubClient) -> None:
    entries = [{"path": "a.py", "type": "blob"}, {"path": 5}, "junk"]
    route(router, f"{REPO}/git/trees/{SHA}").respond(200, json={"tree": entries, "truncated": True})
    assert await gh.get_tree("octo", "repo", SHA) == [{"path": "a.py", "type": "blob"}]


async def test_get_tree_non_dict(router: respx.MockRouter, gh: GitHubClient) -> None:
    route(router, f"{REPO}/git/trees/{SHA}").respond(200, json=[])
    assert await gh.get_tree("octo", "repo", SHA) == []


async def test_commit_stats_from_link_header(router: respx.MockRouter, gh: GitHubClient) -> None:
    link = '<https://api.github.com/repositories/1/commits?sha=x&per_page=1&page=88>; rel="last"'
    commit = {"commit": {"author": {"date": "2026-01-02T03:04:05Z"}}}
    route(router, f"{REPO}/commits").respond(200, json=[commit], headers={"Link": link})
    count, last = await gh.get_commit_stats("octo", "repo", SHA)
    assert count == 88
    assert last is not None and last.year == 2026


async def test_commit_stats_without_link(router: respx.MockRouter, gh: GitHubClient) -> None:
    route(router, f"{REPO}/commits").respond(200, json=[{"commit": {}}])
    assert await gh.get_commit_stats("octo", "repo", SHA) == (1, None)


@pytest.mark.parametrize(
    "response",
    [httpx.Response(409, json={}), httpx.Response(404, json={}), httpx.Response(200, json=[])],
)
async def test_commit_stats_empty(
    router: respx.MockRouter, gh: GitHubClient, response: httpx.Response
) -> None:
    route(router, f"{REPO}/commits").mock(return_value=response)
    assert await gh.get_commit_stats("octo", "repo", SHA) == (0, None)


@pytest.mark.parametrize(
    "response", [httpx.Response(400, json={}), httpx.Response(200, text="nope")]
)
async def test_commit_stats_errors(
    router: respx.MockRouter, gh: GitHubClient, response: httpx.Response
) -> None:
    route(router, f"{REPO}/commits").mock(return_value=response)
    with pytest.raises(GitHubUnavailableError):
        await gh.get_commit_stats("octo", "repo", SHA)


# ---------------------------------------------------------------------------- file contents


async def test_get_file_text(router: respx.MockRouter, gh: GitHubClient) -> None:
    file_route = route(router, f"{REPO}/contents/src/app.py").respond(200, content=b"x = 1\n")
    assert await gh.get_file_text("octo", "repo", "src/app.py", SHA) == ("x = 1\n", False)
    request = file_route.calls.last.request
    assert request.url.params["ref"] == SHA
    assert request.headers["Accept"] == "application/vnd.github.raw"


async def test_get_file_text_truncates(router: respx.MockRouter, gh: GitHubClient) -> None:
    route(router, f"{REPO}/contents/big.py").respond(200, content=b"a" * 5000)
    text, truncated = await gh.get_file_text("octo", "repo", "big.py", SHA, max_bytes=100)  # type: ignore[misc]
    assert text == "a" * 100
    assert truncated


async def test_get_file_text_exact_size_not_truncated(
    router: respx.MockRouter, gh: GitHubClient
) -> None:
    route(router, f"{REPO}/contents/f.py").respond(200, content=b"a" * 100)
    assert await gh.get_file_text("octo", "repo", "f.py", SHA, max_bytes=100) == ("a" * 100, False)


async def test_get_file_text_binary_returns_none(
    router: respx.MockRouter, gh: GitHubClient
) -> None:
    route(router, f"{REPO}/contents/logo.dat").respond(200, content=b"\x89PNG\x00\x00\x00")
    assert await gh.get_file_text("octo", "repo", "logo.dat", SHA) is None


async def test_get_file_text_missing_returns_none(
    router: respx.MockRouter, gh: GitHubClient
) -> None:
    route(router, f"{REPO}/contents/gone.py").respond(404, json={})
    assert await gh.get_file_text("octo", "repo", "gone.py", SHA) is None


async def test_get_file_text_unsafe_path_returns_none(gh: GitHubClient) -> None:
    assert await gh.get_file_text("octo", "repo", "../secrets", SHA) is None


@pytest.mark.parametrize(
    "mock_kwargs",
    [
        {"return_value": httpx.Response(429, json={})},
        {"return_value": httpx.Response(500, json={})},
        {"side_effect": httpx.ReadTimeout("slow")},
    ],
)
async def test_get_file_text_unavailable(
    router: respx.MockRouter, gh: GitHubClient, mock_kwargs: dict[str, object]
) -> None:
    route(router, f"{REPO}/contents/a.py").mock(**mock_kwargs)  # type: ignore[arg-type]
    with pytest.raises(GitHubUnavailableError):
        await gh.get_file_text("octo", "repo", "a.py", SHA)


class _BrokenStream(httpx.AsyncByteStream):
    async def __aiter__(self) -> AsyncIterator[bytes]:
        yield b"partial"
        raise httpx.ReadError("connection reset")


async def test_get_file_text_stream_error(router: respx.MockRouter, gh: GitHubClient) -> None:
    route(router, f"{REPO}/contents/a.py").mock(
        return_value=httpx.Response(200, stream=_BrokenStream())
    )
    with pytest.raises(GitHubUnavailableError):
        await gh.get_file_text("octo", "repo", "a.py", SHA)
