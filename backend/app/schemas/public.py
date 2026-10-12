"""Public (unauthenticated) roast schemas. Never include private user fields such as email."""

from datetime import datetime

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
    author: PublicAuthor
    roast: RoastResponse
    analysis: PublicAnalysisSummary
    created_at: datetime
