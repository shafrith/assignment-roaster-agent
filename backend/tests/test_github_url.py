"""GitHub URL validation: the SSRF boundary of the roaster."""

import pytest

from app.exceptions import BadRequestError
from app.services.github_url import (
    INVALID_URL_MESSAGE,
    normalize_github_url,
    parse_github_url,
)

GOOD_URLS = [
    ("https://github.com/octocat/hello-world", ("octocat", "hello-world")),
    ("http://github.com/octocat/hello-world", ("octocat", "hello-world")),
    ("https://www.github.com/octocat/hello-world", ("octocat", "hello-world")),
    ("HTTPS://GitHub.com/OctoCat/Hello.World", ("OctoCat", "Hello.World")),
    ("https://github.com/octocat/hello-world.git", ("octocat", "hello-world")),
    ("https://github.com/octocat/hello-world.GIT", ("octocat", "hello-world")),
    ("https://github.com/octocat/hello-world/", ("octocat", "hello-world")),
    ("https://github.com/octocat/hello-world/tree/main/src", ("octocat", "hello-world")),
    ("https://github.com/octocat/hello-world/blob/main/app.py", ("octocat", "hello-world")),
    ("https://github.com/octocat/hello-world?tab=readme-ov-file", ("octocat", "hello-world")),
    ("https://github.com/octocat/hello-world#readme", ("octocat", "hello-world")),
    ("  https://github.com/octocat/hello-world  ", ("octocat", "hello-world")),
    ("https://github.com/a/b", ("a", "b")),
    ("https://github.com/my-org-1/repo_name-2", ("my-org-1", "repo_name-2")),
    ("https://github.com/octocat/.github", ("octocat", ".github")),
]

BAD_URLS = [
    "",
    "   ",
    "github.com/octocat/hello-world",  # no scheme
    "ftp://github.com/octocat/hello-world",
    "javascript:alert(1)",
    "file:///etc/passwd",
    "https://gitlab.com/octocat/hello-world",
    "https://github.com.evil.com/octocat/hello-world",
    "https://evil.com/github.com/octocat/hello-world",
    "https://api.github.com/repos/octocat/hello-world",
    "https://gist.github.com/octocat/abc123",
    "https://raw.githubusercontent.com/octocat/hello-world/main/README.md",
    "https://user@github.com/octocat/hello-world",
    "https://user:pass@github.com/octocat/hello-world",
    "https://github.com@evil.com/octocat/hello-world",
    "https://github.com:443/octocat/hello-world",
    "https://github.com:8080/octocat/hello-world",
    "https://github.com./octocat/hello-world",
    "https://github.com",
    "https://github.com/",
    "https://github.com/octocat",
    "https://github.com/octocat/",
    "https://github.com/orgs/octocat",
    "https://github.com/settings/profile",
    "https://github.com/marketplace/actions",
    "https://github.com/login/oauth",
    "https://github.com/topics/python",
    "https://github.com/octocat%2Fhello-world/x",
    "https://github.com/octocat/hello%2F..%2Fworld",
    "https://github.com/octo%2e%2e/repo",
    "https://github.com/-octocat/hello-world",
    "https://github.com/octocat-/hello-world",
    "https://github.com/" + "a" * 40 + "/repo",
    "https://github.com/octocat/" + "r" * 101,
    "https://github.com/octocat/hello world",
    "https://github.com/octocat/hello\tworld",
    "https://github.com\\octocat\\hello-world",
    "https://github.com/octocat/..",
    "https://github.com/octocat/.",
    "https://github.com/octocat/.git",
    "https://github.com/octo_cat/hello-world",
    "https://github.com/octocat/hello$world",
    "https://[::1]/octocat/hello-world",
    "https://[::1/octocat/hello-world",  # urlsplit ValueError
    "https://github.com/octocat/hello-world" + "/x" * 300,
]


@pytest.mark.parametrize(("url", "expected"), GOOD_URLS)
def test_valid_urls_parse(url: str, expected: tuple[str, str]) -> None:
    assert parse_github_url(url) == expected


@pytest.mark.parametrize("url", BAD_URLS)
def test_invalid_urls_rejected(url: str) -> None:
    with pytest.raises(BadRequestError) as exc_info:
        parse_github_url(url)
    assert exc_info.value.detail == INVALID_URL_MESSAGE
    assert exc_info.value.status_code == 400


def test_non_string_rejected() -> None:
    with pytest.raises(BadRequestError):
        parse_github_url(None)  # type: ignore[arg-type]


def test_normalize() -> None:
    assert normalize_github_url("OctoCat", "repo") == "https://github.com/OctoCat/repo"
