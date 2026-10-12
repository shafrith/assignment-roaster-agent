"""Submission request/response schemas."""

from datetime import datetime

from pydantic import Field

from app.models.submission import Submission, SubmissionStatus
from app.schemas.analysis import AnalysisSummary
from app.schemas.common import CamelModel
from app.schemas.roast import RoastResponse


class SubmissionCreate(CamelModel):
    """Body of ``POST /submissions``: ``{"repoUrl": "..."}``."""

    repo_url: str = Field(min_length=1, max_length=500)


class VisibilityUpdate(CamelModel):
    """Body of ``PATCH /submissions/{id}/visibility``: ``{"isPublic": true}``."""

    is_public: bool


class SubmissionResponse(CamelModel):
    """Full submission with its analysis summary and roast (when available)."""

    id: int
    repo_url: str
    repo_owner: str
    repo_name: str
    status: SubmissionStatus
    error_message: str | None
    is_public: bool
    share_slug: str
    created_at: datetime
    completed_at: datetime | None
    analysis: AnalysisSummary | None
    roast: RoastResponse | None


class SubmissionListItem(CamelModel):
    """Compact row for the dashboard table."""

    id: int
    repo_owner: str
    repo_name: str
    status: SubmissionStatus
    score: float | None
    verdict_title: str | None
    is_public: bool
    created_at: datetime

    @classmethod
    def from_submission(cls, submission: Submission) -> "SubmissionListItem":
        """Build a list item, flattening the roast's score and verdict (null if not roasted).

        Args:
            submission: Submission with its ``roast`` relationship loaded.

        Returns:
            The list item schema.
        """
        roast = submission.roast
        return cls(
            id=submission.id,
            repo_owner=submission.repo_owner,
            repo_name=submission.repo_name,
            status=submission.status,
            score=float(roast.score) if roast is not None else None,
            verdict_title=roast.verdict_title if roast is not None else None,
            is_public=submission.is_public,
            created_at=submission.created_at,
        )
