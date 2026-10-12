"""Submission endpoints: create, list, fetch, retry, visibility, delete."""

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request, Response, status
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.rate_limit import limiter, user_or_ip_key
from app.schemas.common import Paginated
from app.schemas.submission import (
    SubmissionCreate,
    SubmissionListItem,
    SubmissionResponse,
    VisibilityUpdate,
)
from app.services import submission_service
from app.services.pipeline import run_pipeline

router = APIRouter(prefix="/submissions", tags=["submissions"])


@router.post("", response_model=SubmissionResponse, status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("10/minute", key_func=user_or_ip_key)
async def create_submission(
    request: Request,
    body: SubmissionCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SubmissionResponse:
    """Create a submission for a public GitHub repo and schedule the roast pipeline."""
    submission = submission_service.create_submission(db, user, body.repo_url)
    background_tasks.add_task(run_pipeline, submission.id)
    return SubmissionResponse.model_validate(submission)


@router.get("", response_model=Paginated[SubmissionListItem])
async def list_submissions(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=50, alias="pageSize"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Paginated[SubmissionListItem]:
    """List the caller's submissions, newest first."""
    items, total = submission_service.list_submissions(db, user, page, page_size)
    return Paginated[SubmissionListItem](
        items=[SubmissionListItem.from_submission(s) for s in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{submission_id}", response_model=SubmissionResponse)
async def get_submission(
    submission_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SubmissionResponse:
    """Fetch one of the caller's submissions (404 if not owned)."""
    submission = submission_service.get_owned_submission(db, user, submission_id)
    return SubmissionResponse.model_validate(submission)


@router.post(
    "/{submission_id}/retry",
    response_model=SubmissionResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
@limiter.limit("10/minute", key_func=user_or_ip_key)
async def retry_submission(
    request: Request,
    submission_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SubmissionResponse:
    """Re-run the pipeline for a failed submission (409 unless ``failed``)."""
    submission = submission_service.retry_submission(db, user, submission_id)
    background_tasks.add_task(run_pipeline, submission.id)
    return SubmissionResponse.model_validate(submission)


@router.patch("/{submission_id}/visibility", response_model=SubmissionResponse)
async def update_visibility(
    submission_id: int,
    body: VisibilityUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SubmissionResponse:
    """Make the roast public or private."""
    submission = submission_service.set_visibility(db, user, submission_id, body.is_public)
    return SubmissionResponse.model_validate(submission)


@router.delete("/{submission_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_submission(
    submission_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    """Delete one of the caller's submissions."""
    submission_service.delete_submission(db, user, submission_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
