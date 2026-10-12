"""Shared data contracts between the repo analyzer, roast engine, and submission pipeline.

These types are the hand-off points between services built in parallel. Change them only in
coordination with every consumer:

- ``github_client`` / ``repo_analyzer`` produce ``RepoInfo`` and ``AnalysisResult``.
- ``roast_engine`` consumes ``AnalysisResult`` and produces ``RoastResult``.
- ``pipeline`` orchestrates them and persists results to ``RepoAnalysis`` / ``Roast`` rows.
"""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, ClassVar, Literal

from fastapi import status

from app.exceptions import AppError

Severity = Literal["low", "medium", "high", "critical"]
IssueCategory = Literal[
    "structure",
    "documentation",
    "dependencies",
    "testing",
    "security",
    "code_quality",
    "git_hygiene",
    "genai_practices",
]


@dataclass(frozen=True)
class Finding:
    """A single issue detected by static analysis or reported by the roast engine."""

    category: IssueCategory
    severity: Severity
    message: str
    file: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize for JSONB storage (``findings`` / ``issues`` columns)."""
        return {
            "category": self.category,
            "severity": self.severity,
            "file": self.file,
            "message": self.message,
        }


@dataclass(frozen=True)
class RepoInfo:
    """Public repository metadata resolved from the GitHub API."""

    owner: str
    name: str
    default_branch: str
    head_sha: str
    size_kb: int
    is_private: bool


@dataclass(frozen=True)
class SampledFile:
    """A source file selected for the LLM prompt. ``content`` is ALREADY secret-redacted."""

    path: str
    content: str
    truncated: bool = False


@dataclass
class AnalysisResult:
    """Output of ``repo_analyzer.analyze_repo``. Field names mirror the ``RepoAnalysis`` model."""

    languages: dict[str, int] = field(default_factory=dict)
    file_count: int = 0
    total_lines: int = 0
    notebook_count: int = 0
    has_readme: bool = False
    readme_word_count: int = 0
    has_tests: bool = False
    has_dependency_file: bool = False
    has_gitignore: bool = False
    has_env_file_committed: bool = False
    secrets_found_count: int = 0
    commit_count: int = 0
    last_commit_at: datetime | None = None
    largest_files: list[dict[str, Any]] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)
    sampled_files: list[SampledFile] = field(default_factory=list)

    def to_model_kwargs(self) -> dict[str, Any]:
        """Return kwargs for constructing a ``RepoAnalysis`` row (file contents are NOT stored)."""
        return {
            "languages": self.languages,
            "file_count": self.file_count,
            "total_lines": self.total_lines,
            "notebook_count": self.notebook_count,
            "has_readme": self.has_readme,
            "readme_word_count": self.readme_word_count,
            "has_tests": self.has_tests,
            "has_dependency_file": self.has_dependency_file,
            "has_gitignore": self.has_gitignore,
            "has_env_file_committed": self.has_env_file_committed,
            "secrets_found_count": self.secrets_found_count,
            "commit_count": self.commit_count,
            "last_commit_at": self.last_commit_at,
            "largest_files": self.largest_files,
            "findings": [f.to_dict() for f in self.findings],
            "sampled_files": [f.path for f in self.sampled_files],
        }


@dataclass
class RoastResult:
    """Output of ``roast_engine.generate_roast``. Field names mirror the ``Roast`` model."""

    score: Decimal
    verdict_title: str
    roast_text: str
    strengths: list[str]
    issues: list[Finding]
    fix_tips: list[str]
    model: str
    input_tokens: int
    output_tokens: int

    def to_model_kwargs(self) -> dict[str, Any]:
        """Return kwargs for constructing a ``Roast`` row."""
        return {
            "score": self.score,
            "verdict_title": self.verdict_title,
            "roast_text": self.roast_text,
            "strengths": self.strengths,
            "issues": [i.to_dict() for i in self.issues],
            "fix_tips": self.fix_tips,
            "model": self.model,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
        }


class PipelineError(AppError):
    """Expected pipeline failure. ``detail`` is a user-safe (Tanglish) message stored on the
    submission's ``error_message``."""

    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Roast panna mudiyala machan, konjam neram kazhichu retry pannu 🙏"
    # False when re-running the pipeline cannot succeed (retry is refused with 409).
    retryable: ClassVar[bool] = True


class RepoNotFoundError(PipelineError):
    """Repo does not exist or is private."""

    status_code = status.HTTP_404_NOT_FOUND
    default_detail = "Repo private-a illa exist-e aagala pola 🤔"
    retryable = False


class RepoTooLargeError(PipelineError):
    """Repo exceeds ``MAX_REPO_SIZE_MB``."""

    default_detail = "Repo romba perusu da, 50MB-kku mela! 🐘"
    retryable = False


class GitHubUnavailableError(PipelineError):
    """GitHub API error, timeout, or rate limit."""

    status_code = status.HTTP_502_BAD_GATEWAY
    default_detail = "GitHub-ae konjam tired-a irukku, apram try pannu 😴"


class RoastGenerationError(PipelineError):
    """LLM API failure or invalid structured output after retry."""

    status_code = status.HTTP_502_BAD_GATEWAY
    default_detail = "AI-kku roast panna mood illa, retry pannu 🔁"
