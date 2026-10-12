"""User profile schemas (camelCase on the wire). Email is never exposed."""

from datetime import datetime

from app.schemas.common import CamelModel


class UserResponse(CamelModel):
    """The authenticated user's profile."""

    id: int
    github_username: str
    display_name: str | None
    avatar_url: str | None
    default_roast_public: bool
    created_at: datetime
    # Quota: ROAST_DAILY_LIMIT and the attempts (creates + retries) used in the last 24h.
    daily_limit: int = 0
    roasts_used_today: int = 0


class UserSettingsUpdate(CamelModel):
    """``{defaultRoastPublic}`` body for ``PATCH /auth/me``."""

    default_roast_public: bool
