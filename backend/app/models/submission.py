"""Submission model: one roast request for a GitHub repository."""

import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    func,
    text,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin

if TYPE_CHECKING:
    from app.models.repo_analysis import RepoAnalysis
    from app.models.roast import Roast
    from app.models.user import User


class SubmissionStatus(enum.StrEnum):
    """Pipeline state of a submission (PG enum ``submission_status``)."""

    pending = "pending"
    analyzing = "analyzing"
    roasting = "roasting"
    completed = "completed"
    failed = "failed"


class Submission(TimestampMixin, Base):
    __tablename__ = "submissions"
    __table_args__ = (
        # Dashboard list (newest first) and the per-user quota/ownership filters.
        Index("ix_submissions_user_created", "user_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    # Normalized https://github.com/{owner}/{repo}
    repo_url: Mapped[str] = mapped_column(String(300), nullable=False)
    repo_owner: Mapped[str] = mapped_column(String(100), nullable=False)
    repo_name: Mapped[str] = mapped_column(String(100), nullable=False)
    default_branch: Mapped[str | None] = mapped_column(String(100), nullable=True)
    commit_sha: Mapped[str | None] = mapped_column(String(40), nullable=True)
    status: Mapped[SubmissionStatus] = mapped_column(
        Enum(
            SubmissionStatus,
            name="submission_status",
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        default=SubmissionStatus.pending,
        server_default=SubmissionStatus.pending.value,
        nullable=False,
    )
    # User-safe (Tanglish) message only; never raw exceptions.
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # False for deterministic failures (private/missing repo, repo too large): retry is refused.
    error_retryable: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=true(), nullable=False
    )
    # Set when the roast was copied from another submission of the same repo + commit.
    deduped_from_submission_id: Mapped[int | None] = mapped_column(
        ForeignKey("submissions.id", ondelete="SET NULL"), nullable=True
    )
    # The service layer sets this from user.default_roast_public; True is only a fallback.
    is_public: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=true(), nullable=False
    )
    share_slug: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship(back_populates="submissions")
    analysis: Mapped["RepoAnalysis | None"] = relationship(
        back_populates="submission",
        uselist=False,
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    roast: Mapped["Roast | None"] = relationship(
        back_populates="submission",
        uselist=False,
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return (
            f"<Submission id={self.id} repo={self.repo_owner}/{self.repo_name} "
            f"status={self.status}>"
        )


# Dedupe lookup in the pipeline: same commit, case-insensitive owner/repo, completed only.
Index(
    "ix_submissions_dedupe",
    Submission.commit_sha,
    func.lower(Submission.repo_owner),
    func.lower(Submission.repo_name),
    postgresql_where=text("status = 'completed'"),
)
