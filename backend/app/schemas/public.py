"""Public (unauthenticated) roast schemas. Never include private user fields such as email."""

from datetime import datetime

from app.models.submission import Submission, SubmissionStatus
from app.schemas.common import CamelModel
from app.schemas.roast import RoastResponse


class PublicAuthor(CamelModel):
    """Public author identity: GitHub username and avatar only."""

    github_username: str
    avatar_url: str | None


class PublicAnalysisSummary(CamelModel):
    """Analysis chips safe for anonymous viewers.

    Deliberately omits ``secretsFoundCount`` and ``hasEnvFileCommitted`` (owner-only), so the
    public share pages are not an index of repos with committed credentials (SEC-8).
    """

    languages: dict[str, int]
    file_count: int
    has_readme: bool
    has_tests: bool
    has_dependency_file: bool
    commit_count: int


class PublicRoastResponse(CamelModel):
    """A shared roast, served at ``/public/roasts/{share_slug}``."""

    repo_url: str
    repo_owner: str
    repo_name: str
    # None for anonymous (no-login) roasts.
    author: PublicAuthor | None
    roast: RoastResponse
    analysis: PublicAnalysisSummary
    created_at: datetime


class RoastStatusResponse(CamelModel):
    """A roast in any status, served at ``/roasts/{share_slug}`` to the no-login result page.

    Uses the public analysis summary: the link may be shared, so secret counts stay hidden.
    """

    share_slug: str
    repo_url: str
    repo_owner: str
    repo_name: str
    status: SubmissionStatus
    error_message: str | None
    # Lets the UI hide the retry button for deterministic failures.
    error_retryable: bool
    author: PublicAuthor | None
    analysis: PublicAnalysisSummary | None
    roast: RoastResponse | None
    created_at: datetime
    completed_at: datetime | None

    @classmethod
    def from_submission(cls, submission: Submission) -> "RoastStatusResponse":
        """Build the response; analysis and roast are only exposed once the roast completed.

        Args:
            submission: Submission with ``user``, ``analysis`` and ``roast`` loadable.

        Returns:
            The response schema.
        """
        completed = submission.status == SubmissionStatus.completed
        return cls.model_validate(
            {
                "share_slug": submission.share_slug,
                "repo_url": submission.repo_url,
                "repo_owner": submission.repo_owner,
                "repo_name": submission.repo_name,
                "status": submission.status,
                "error_message": submission.error_message,
                "error_retryable": submission.error_retryable,
                "author": submission.user,
                "analysis": submission.analysis if completed else None,
                "roast": submission.roast if completed else None,
                "created_at": submission.created_at,
                "completed_at": submission.completed_at,
            }
        )
