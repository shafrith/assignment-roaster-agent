"""Authentication request/response schemas (camelCase on the wire)."""

from typing import Literal

from pydantic import Field

from app.schemas.common import CamelModel


class TokenResponse(CamelModel):
    """``{accessToken, refreshToken, tokenType}``."""

    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"


class RefreshRequest(CamelModel):
    """``{refreshToken}`` body for ``POST /auth/refresh``."""

    refresh_token: str = Field(min_length=1, max_length=512)


class LogoutRequest(CamelModel):
    """``{refreshToken}`` body for ``POST /auth/logout``."""

    refresh_token: str = Field(min_length=1, max_length=512)
