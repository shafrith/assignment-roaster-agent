"""Public share endpoint: a completed roast by its share slug."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.rate_limit import limiter
from app.schemas.public import PublicRoastResponse
from app.services import submission_service

router = APIRouter(prefix="/public", tags=["public"])


@router.get("/roasts/{share_slug}", response_model=PublicRoastResponse)
@limiter.limit("60/minute")
async def get_public_roast(
    request: Request, share_slug: str, db: Session = Depends(get_db)
) -> PublicRoastResponse:
    """Return a public, completed roast by its share slug (404 otherwise)."""
    submission = submission_service.get_public_roast(db, share_slug)
    return PublicRoastResponse.model_validate(
        {
            "repo_url": submission.repo_url,
            "repo_owner": submission.repo_owner,
            "repo_name": submission.repo_name,
            "roast": submission.roast,
            "analysis": submission.analysis,
            "created_at": submission.created_at,
        }
    )
