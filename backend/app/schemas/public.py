"""Public roast schemas (no login). Never expose secret counts, token usage or internal ids."""

from datetime import datetime

from pydantic import Field

from app.models.submission import Submission, SubmissionStatus
from app.schemas.common import CamelModel
from app.schemas.roast import RoastResponse


class RoastCreate(CamelModel):
    """Body of ``POST /roasts``: ``{"repoUrl": "..."}``."""

    repo_url: str = Field(min_length=1, max_length=500)


class PublicAnalysisSummary(CamelModel):
    """Analysis chips safe for anyone holding the link.

    Deliberately omits the secrets count and ``.env``-committed flag, so roast pages are not an
    index of repos with committed credentials (SEC-8).
    """

    languages: dict[str, int]
    file_count: int
    has_readme: bool
    has_tests: bool
    has_dependency_file: bool
    commit_count: int


class PublicRoastResponse(CamelModel):
    """A completed roast, served at ``/public/roasts/{share_slug}``."""

    repo_url: str
    repo_owner: str
    repo_name: str
    roast: RoastResponse
    analysis: PublicAnalysisSummary
    created_at: datetime


class RoastStatusResponse(CamelModel):
    """A roast in any status, served at ``/roasts/{share_slug}`` to the result page.

    ``analysis`` and ``roast`` are only set once the roast completed.
    """

    share_slug: str
    repo_url: str
    repo_owner: str
    repo_name: str
    status: SubmissionStatus
    error_message: str | None
    # Lets the UI hide the retry button for deterministic failures.
    error_retryable: bool
    analysis: PublicAnalysisSummary | None
    roast: RoastResponse | None
    created_at: datetime
    completed_at: datetime | None

    @classmethod
    def from_submission(cls, submission: Submission) -> "RoastStatusResponse":
        """Build the response; analysis and roast are only exposed once the roast completed.

        Args:
            submission: Submission with ``analysis`` and ``roast`` loadable.

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
                "analysis": submission.analysis if completed else None,
                "roast": submission.roast if completed else None,
                "created_at": submission.created_at,
                "completed_at": submission.completed_at,
            }
        )
