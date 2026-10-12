"""Roast response schemas exposed to clients."""

from datetime import datetime

from app.schemas.common import CamelModel
from app.services.contracts import IssueCategory, Severity


class RoastIssue(CamelModel):
    """A single issue called out in the roast."""

    category: IssueCategory
    severity: Severity
    file: str | None = None
    message: str


class RoastResponse(CamelModel):
    """The generated roast. ``score`` is serialized as a JSON number (not a string)."""

    score: float
    verdict_title: str
    roast_text: str
    strengths: list[str]
    issues: list[RoastIssue]
    fix_tips: list[str]
    created_at: datetime
