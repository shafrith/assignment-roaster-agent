"""LLM-generated roast for a submission."""

from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import CheckConstraint, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import CreatedAtMixin

if TYPE_CHECKING:
    from app.models.submission import Submission


class Roast(CreatedAtMixin, Base):
    __tablename__ = "roasts"
    __table_args__ = (CheckConstraint("score >= 0 AND score <= 10", name="score_range"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    submission_id: Mapped[int] = mapped_column(
        ForeignKey("submissions.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    score: Mapped[Decimal] = mapped_column(Numeric(3, 1), nullable=False)
    verdict_title: Mapped[str] = mapped_column(String(120), nullable=False)
    # Tanglish markdown
    roast_text: Mapped[str] = mapped_column(Text, nullable=False)
    strengths: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    # [{category, severity, file, message}]
    issues: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    fix_tips: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # ``app.services.prompts.PROMPT_VERSION`` used to generate it; part of the dedupe key so a
    # prompt change invalidates old roasts. NULL for roasts made before versioning.
    prompt_version: Mapped[str | None] = mapped_column(String(40), nullable=True)

    submission: Mapped["Submission"] = relationship(back_populates="roast")

    def __repr__(self) -> str:
        return f"<Roast id={self.id} submission_id={self.submission_id} score={self.score}>"
