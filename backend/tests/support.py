"""Shared test helpers: a GitHub API mock backed by the eval fixture repos and a fake OpenAI."""

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from urllib.parse import unquote

import httpx
import respx

EVAL_REPOS_DIR = Path(__file__).parent / "fixtures" / "eval_repos"
GITHUB_API_HOST = "api.github.com"

# Fake credentials planted in the messy fixture repo; they must never leave the analyzer.
FIXTURE_SECRETS = (
    "sk-ant-FAKEFAKEFAKEFAKEFAKEFAKEFAKEFAKE",
    "sk-FAKEFAKEFAKEFAKEFAKEFAKEFAKE",
    "FAKEFAKEFAKEFAKE",
)


class FixtureRepo:
    """Serves one eval fixture repo (``tree.json`` + ``files/``) like the GitHub REST API."""

    def __init__(
        self,
        name: str,
        *,
        owner: str | None = None,
        repo: str | None = None,
        private: bool = False,
        size_kb: int | None = None,
    ) -> None:
        self.dir = EVAL_REPOS_DIR / name
        data = json.loads((self.dir / "tree.json").read_text(encoding="utf-8"))
        self.meta: dict[str, Any] = data["repo"]
        self.languages: dict[str, int] = data["languages"]
        self.commits: dict[str, Any] = data["commits"]
        self.tree: list[dict[str, Any]] = data["tree"]
        self.owner = owner or self.meta["owner"]
        self.name = repo or self.meta["name"]
        self.private = private
        self.size_kb = self.meta["size_kb"] if size_kb is None else size_kb
        self.head_sha: str = self.meta["head_sha"]
        self.default_branch: str = self.meta["default_branch"]
        self.content_requests: list[str] = []

    @property
    def url(self) -> str:
        """The github.com URL a user would submit."""
        return f"https://github.com/{self.owner}/{self.name}"

    def file_bytes(self, path: str) -> bytes | None:
        """Return a blob's bytes from ``files/`` (or None when it has no file on disk)."""
        for entry in self.tree:
            if entry["path"] == path and entry["type"] == "blob":
                on_disk = self.dir / "files" / entry.get("fixture_file", path)
                return on_disk.read_bytes() if on_disk.is_file() else None
        return None

    def handle(self, request: httpx.Request) -> httpx.Response | None:
        """Answer ``request`` if it targets this repo, else None."""
        path = unquote(request.url.path)
        prefix = f"/repos/{self.owner}/{self.name}".lower()  # GitHub ignores case here
        if path.lower() != prefix and not path.lower().startswith(prefix + "/"):
            return None
        rest = path[len(prefix) :]
        if rest == "":
            return httpx.Response(
                200,
                json={
                    "name": self.name,
                    "owner": {"login": self.owner},
                    "default_branch": self.default_branch,
                    "size": self.size_kb,
                    "private": self.private,
                    "visibility": "private" if self.private else "public",
                },
            )
        if rest == f"/branches/{self.default_branch}":
            return httpx.Response(200, json={"commit": {"sha": self.head_sha}})
        if rest == "/languages":
            return httpx.Response(200, json=self.languages)
        if rest == f"/git/trees/{self.head_sha}":
            return httpx.Response(200, json={"tree": self.tree, "truncated": False})
        if rest == "/commits":
            count = self.commits["count"]
            link = (
                f'<https://api.github.com/repositories/1/commits?per_page=1&page=2>; rel="next", '
                f"<https://api.github.com/repositories/1/commits?per_page=1&page={count}>; "
                'rel="last"'
            )
            commit = {"commit": {"committer": {"date": self.commits["last_commit_at"]}}}
            return httpx.Response(200, json=[commit], headers={"Link": link})
        if rest.startswith("/contents/"):
            file_path = rest[len("/contents/") :]
            self.content_requests.append(file_path)
            content = self.file_bytes(file_path)
            if content is None:
                return httpx.Response(404, json={"message": "Not Found"})
            return httpx.Response(200, content=content)
        return httpx.Response(404, json={"message": "Not Found"})


def mock_github_repos(router: respx.MockRouter, *repos: FixtureRepo) -> respx.Route:
    """Route every ``api.github.com`` request on ``router`` to the given fixture repos."""

    def dispatch(request: httpx.Request) -> httpx.Response:
        for repo in repos:
            response = repo.handle(request)
            if response is not None:
                return response
        return httpx.Response(404, json={"message": "Not Found"})

    return router.route(host=GITHUB_API_HOST).mock(side_effect=dispatch)


# ---------------------------------------------------------------------------- fake OpenAI


def roast_input(**overrides: Any) -> dict[str, Any]:
    """A valid ``submit_roast`` tool input; keyword arguments override fields."""
    data: dict[str, Any] = {
        "score": 7.5,
        "verdict_title": "Production Ready Ponnusamy",
        "roast_text": "Dei machan, enna idhu? README semma, but tests konjam kammi da. 🔥",
        "strengths": ["Clean folder structure"],
        "issues": [
            {
                "category": "testing",
                "severity": "medium",
                "file": None,
                "message": "Only one test file.",
            }
        ],
        "fix_tips": ["Add more tests.", "Pin dependencies.", "Add a CI workflow."],
    }
    data.update(overrides)
    return data


def tool_response(
    tool_input: dict[str, Any] | str | None = None,
    *,
    input_tokens: int = 1000,
    output_tokens: int = 300,
    model: str = "gpt-test-model",
    finish_reason: str = "stop",
    name: str = "submit_roast",
    refusal: str | None = None,
) -> SimpleNamespace:
    """A Chat Completions-like response with one ``submit_roast`` function call.

    ``tool_input`` may be a dict (JSON-encoded as the call's arguments) or a raw string.
    """
    data = roast_input() if tool_input is None else tool_input
    arguments = data if isinstance(data, str) else json.dumps(data)
    call = SimpleNamespace(
        id="call_test",
        type="function",
        function=SimpleNamespace(name=name, arguments=arguments),
    )
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                index=0,
                finish_reason=finish_reason,
                message=SimpleNamespace(
                    role="assistant", content=None, refusal=refusal, tool_calls=[call]
                ),
            )
        ],
        model=model,
        usage=SimpleNamespace(prompt_tokens=input_tokens, completion_tokens=output_tokens),
    )


def text_response(text: str = "Sorry, here is my roast as text.") -> SimpleNamespace:
    """A response with only text content (no function call)."""
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                index=0,
                finish_reason="stop",
                message=SimpleNamespace(
                    role="assistant", content=text, refusal=None, tool_calls=None
                ),
            )
        ],
        model="gpt-test-model",
        usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5),
    )


class FakeCompletions:
    """``client.chat.completions`` stand-in: returns (or raises) queued items in order.

    When one item is left it is reused for every further call.
    """

    def __init__(self, outputs: list[Any]) -> None:
        self.outputs = outputs
        self.calls: list[dict[str, Any]] = []

    async def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        item = self.outputs.pop(0) if len(self.outputs) > 1 else self.outputs[0]
        if isinstance(item, BaseException):
            raise item
        return item


class FakeOpenAI:
    """Minimal ``AsyncOpenAI`` stand-in."""

    def __init__(self, *outputs: Any) -> None:
        self.completions = FakeCompletions(list(outputs) or [tool_response()])
        self.chat = SimpleNamespace(completions=self.completions)
        self.closed = False

    def set_outputs(self, *outputs: Any) -> None:
        """Replace the queued responses."""
        self.completions.outputs = list(outputs)

    @property
    def calls(self) -> list[dict[str, Any]]:
        return self.completions.calls

    @property
    def call_count(self) -> int:
        return len(self.completions.calls)

    def user_prompt(self, index: int = 0) -> str:
        """The user message content of the ``index``-th request."""
        return str(self.calls[index]["messages"][1]["content"])

    async def close(self) -> None:
        self.closed = True
