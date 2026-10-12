"""Static analysis results for a submission's repository."""

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import CreatedAtMixin

if TYPE_CHECKING:
    from app.models.submission import Submission


class RepoAnalysis(CreatedAtMixin, Base):
    __tablename__ = "repo_analyses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    submission_id: Mapped[int] = mapped_column(
        ForeignKey("submissions.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    # {"Python": 12034, ...} as reported by GitHub
    languages: Mapped[dict[str, int]] = mapped_column(JSONB, nullable=False, default=dict)
    file_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Sampled files only
    total_lines: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    notebook_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    has_readme: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    readme_word_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    has_tests: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    has_dependency_file: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    has_gitignore: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    has_env_file_committed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Counts only; raw secret values are never stored.
    secrets_found_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    commit_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_commit_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # [{path, size}] top 5
    largest_files: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    # [{category, severity, file, message}]
    findings: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    # Paths sent to the LLM
    sampled_files: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)

    submission: Mapped["Submission"] = relationship(back_populates="analysis")

    def __repr__(self) -> str:
        return f"<RepoAnalysis id={self.id} submission_id={self.submission_id}>"
