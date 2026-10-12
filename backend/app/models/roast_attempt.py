"""One pipeline run (first attempt or retry) charged against a user's daily roast quota.

Attempts live in their own table rather than as columns on ``submissions`` so that deleting a
submission does not refund quota (``submission_id`` is set to NULL, the row stays), and so the
24h quota is a single indexed count over ``(user_id, created_at)``.
"""

from sqlalchemy import ForeignKey, Index, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import CreatedAtMixin


class RoastAttempt(CreatedAtMixin, Base):
    __tablename__ = "roast_attempts"
    __table_args__ = (Index("ix_roast_attempts_user_created", "user_id", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    # NULL once the submission is deleted; the attempt still counts toward the quota.
    submission_id: Mapped[int | None] = mapped_column(
        ForeignKey("submissions.id", ondelete="SET NULL"), index=True, nullable=True
    )

    def __repr__(self) -> str:
        return (
            f"<RoastAttempt id={self.id} user_id={self.user_id} submission_id={self.submission_id}>"
        )
