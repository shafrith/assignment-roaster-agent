"""One pipeline run (first attempt or retry) charged against a client's daily roast quota.

Attempts are charged to ``client_key``, an HMAC of the client IP (the raw IP is never stored).
They live in their own table rather than as columns on ``submissions`` so the 24h quota is a
single indexed count over ``(client_key, created_at)``.
"""

from sqlalchemy import ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import CreatedAtMixin


class RoastAttempt(CreatedAtMixin, Base):
    __tablename__ = "roast_attempts"
    __table_args__ = (Index("ix_roast_attempts_client_created", "client_key", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # HMAC-SHA256 hex of the client IP. NULL only for attempts from the old login era.
    client_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # NULL once the submission is deleted; the attempt still counts toward the quota.
    submission_id: Mapped[int | None] = mapped_column(
        ForeignKey("submissions.id", ondelete="SET NULL"), index=True, nullable=True
    )

    def __repr__(self) -> str:
        return f"<RoastAttempt id={self.id} submission_id={self.submission_id}>"
