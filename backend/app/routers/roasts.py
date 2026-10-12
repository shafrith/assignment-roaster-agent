"""No-login roast endpoints: paste a GitHub URL, poll the roast by its share slug, retry."""

from fastapi import APIRouter, BackgroundTasks, Depends, Request, status
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.rate_limit import anonymous_client_key, limiter
from app.schemas.public import RoastStatusResponse
from app.schemas.submission import SubmissionCreate
from app.services import submission_service
from app.services.pipeline import run_pipeline

router = APIRouter(prefix="/roasts", tags=["roasts"])


@router.post("", response_model=RoastStatusResponse, status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("10/minute")
async def create_roast(
    request: Request,
    body: SubmissionCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> RoastStatusResponse:
    """Queue a roast of a public GitHub repo without login (quota is per client)."""
    submission = submission_service.create_anonymous_submission(
        db, anonymous_client_key(request), body.repo_url
    )
    background_tasks.add_task(run_pipeline, submission.id)
    return RoastStatusResponse.from_submission(submission)


@router.get("/{share_slug}", response_model=RoastStatusResponse)
@limiter.limit("120/minute")
async def get_roast(
    request: Request, share_slug: str, db: Session = Depends(get_db)
) -> RoastStatusResponse:
    """Return a roast's progress or result by share slug (404 if unknown or private)."""
    submission = submission_service.get_roast_by_slug(db, share_slug)
    return RoastStatusResponse.from_submission(submission)


@router.post(
    "/{share_slug}/retry",
    response_model=RoastStatusResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
@limiter.limit("10/minute")
async def retry_roast(
    request: Request,
    share_slug: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> RoastStatusResponse:
    """Re-run the pipeline for a failed anonymous roast (409 unless ``failed``)."""
    submission = submission_service.retry_anonymous_submission(
        db, anonymous_client_key(request), share_slug
    )
    background_tasks.add_task(run_pipeline, submission.id)
    return RoastStatusResponse.from_submission(submission)
