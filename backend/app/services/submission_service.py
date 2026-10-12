"""Submission business logic: create, list, fetch, retry, visibility, delete, public share."""

import logging
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload, selectinload

from app.config import settings
from app.exceptions import ConflictError, NotFoundError, RateLimitedError
from app.models.roast_attempt import RoastAttempt
from app.models.submission import Submission, SubmissionStatus
from app.models.user import User
from app.services.github_url import normalize_github_url, parse_github_url

logger = logging.getLogger(__name__)

DAILY_LIMIT_MESSAGE = "Innaikku quota mudinjuchu machan, naalaikku vaa! 🙏"
NOT_FOUND_MESSAGE = "Indha roast-a kandupidikka mudiyala machan 🔍"
RETRY_CONFLICT_MESSAGE = "Failed aana roast-a mattum dhaan retry panna mudiyum machan 🔁"
RETRY_NOT_RETRYABLE_MESSAGE = (
    "Indha error retry pannaalum maaradhu machan. Repo-va fix pannittu (public-a, 50MB-kku "
    "keezha) pudhusa submit pannu 🔧"
)
RETRY_LIMIT_MESSAGE = "Indha roast-ku retry limit mudinjuchu machan, pudhusa submit pannu 🛑"
SLUG_MAX_ATTEMPTS = 5
QUOTA_WINDOW = timedelta(hours=24)


def _generate_share_slug() -> str:
    """Return a URL-safe random share slug (~11 chars)."""
    return secrets.token_urlsafe(8)


def _lock_user(db: Session, user: User) -> None:
    """Take a row lock on the user (``SELECT ... FOR UPDATE``) until the transaction ends.

    Serializes quota check + attempt insert per user, so concurrent requests (several workers,
    or threadpool routes) cannot both pass the check (COR-3).
    """
    db.execute(select(User.id).where(User.id == user.id).with_for_update())


def attempts_used_today(db: Session, user_id: int) -> int:
    """Return the number of pipeline attempts (creates + retries) in the last 24 hours.

    Args:
        db: Database session.
        user_id: User whose attempts are counted.

    Returns:
        Attempts charged against the daily quota, including those of deleted submissions.
    """
    since = datetime.now(UTC) - QUOTA_WINDOW
    count = db.scalar(
        select(func.count(RoastAttempt.id)).where(
            RoastAttempt.user_id == user_id, RoastAttempt.created_at >= since
        )
    )
    return int(count or 0)


def _enforce_daily_limit(db: Session, user: User) -> None:
    """Raise when the user already used ``ROAST_DAILY_LIMIT`` attempts in the last 24h.

    Must be called after :func:`_lock_user` in the same transaction.

    Raises:
        RateLimitedError: Quota exhausted.
    """
    if attempts_used_today(db, user.id) >= settings.ROAST_DAILY_LIMIT:
        raise RateLimitedError(DAILY_LIMIT_MESSAGE)


def create_submission(db: Session, user: User, repo_url: str) -> Submission:
    """Validate the repo URL, enforce the daily quota, and insert a pending submission.

    The quota check, the submission insert and its :class:`RoastAttempt` are one transaction
    holding the user's row lock.

    Args:
        db: Request DB session.
        user: Authenticated user.
        repo_url: Raw GitHub repo URL from the client.

    Returns:
        The persisted ``pending`` submission.

    Raises:
        BadRequestError: URL is not a GitHub repo URL.
        RateLimitedError: Daily quota exhausted.
    """
    owner, repo = parse_github_url(repo_url)
    normalized_url = normalize_github_url(owner, repo)

    for attempt in range(1, SLUG_MAX_ATTEMPTS + 1):
        _lock_user(db, user)
        try:
            _enforce_daily_limit(db, user)
        except RateLimitedError:
            db.rollback()
            raise
        submission = Submission(
            user_id=user.id,
            repo_url=normalized_url,
            repo_owner=owner,
            repo_name=repo,
            status=SubmissionStatus.pending,
            is_public=user.default_roast_public,
            share_slug=_generate_share_slug(),
        )
        db.add(submission)
        try:
            db.flush()
            db.add(RoastAttempt(user_id=user.id, submission_id=submission.id))
            db.commit()
        except IntegrityError:
            db.rollback()
            if attempt == SLUG_MAX_ATTEMPTS:
                raise
            logger.warning("Share slug collision on attempt %d; retrying", attempt)
            continue
        db.refresh(submission)
        logger.info("Submission %d created for user %d", submission.id, user.id)
        return submission
    raise RuntimeError("unreachable")  # pragma: no cover


def list_submissions(
    db: Session, user: User, page: int, page_size: int
) -> tuple[list[Submission], int]:
    """Return one page of the user's submissions (newest first) and the total count.

    The ``roast`` relationship is eager-loaded so list items need no extra queries.
    """
    total = db.scalar(select(func.count(Submission.id)).where(Submission.user_id == user.id)) or 0
    items = list(
        db.scalars(
            select(Submission)
            .where(Submission.user_id == user.id)
            .options(selectinload(Submission.roast))
            .order_by(Submission.created_at.desc(), Submission.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )
    return items, total


def get_owned_submission(db: Session, user: User, submission_id: int) -> Submission:
    """Fetch a submission owned by ``user`` with analysis and roast loaded.

    Raises:
        NotFoundError: Missing or owned by someone else (existence is not leaked).
    """
    submission = db.scalar(
        select(Submission)
        .where(Submission.id == submission_id, Submission.user_id == user.id)
        .options(selectinload(Submission.analysis), selectinload(Submission.roast))
    )
    if submission is None:
        raise NotFoundError(NOT_FOUND_MESSAGE)
    return submission


def retry_submission(db: Session, user: User, submission_id: int) -> Submission:
    """Reset a ``failed`` submission to ``pending`` so the pipeline can run again.

    Every retry is a new :class:`RoastAttempt`: it counts toward the daily quota, and a
    submission gets at most ``ROAST_MAX_RETRIES`` retries. Deterministic failures (private or
    missing repo, repo too large) are not retryable. Stale partial ``RepoAnalysis`` / ``Roast``
    rows are deleted. Check and update run under the user and submission row locks.

    Raises:
        NotFoundError: Not found / not owned.
        ConflictError: Not ``failed``, not retryable, or the retry cap is reached.
        RateLimitedError: Daily quota exhausted.
    """
    _lock_user(db, user)
    try:
        submission = db.scalar(
            select(Submission)
            .where(Submission.id == submission_id, Submission.user_id == user.id)
            .with_for_update()
            # The locked row may be newer than an identity-map copy loaded earlier.
            .execution_options(populate_existing=True)
        )
        if submission is None:
            raise NotFoundError(NOT_FOUND_MESSAGE)
        if submission.status != SubmissionStatus.failed:
            raise ConflictError(RETRY_CONFLICT_MESSAGE)
        if not submission.error_retryable:
            raise ConflictError(RETRY_NOT_RETRYABLE_MESSAGE)
        attempts = db.scalar(
            select(func.count(RoastAttempt.id)).where(RoastAttempt.submission_id == submission.id)
        )
        if int(attempts or 0) > settings.ROAST_MAX_RETRIES:
            raise ConflictError(RETRY_LIMIT_MESSAGE)
        _enforce_daily_limit(db, user)
    except (NotFoundError, ConflictError, RateLimitedError):
        db.rollback()
        raise

    if submission.analysis is not None:
        db.delete(submission.analysis)
    if submission.roast is not None:
        db.delete(submission.roast)
    submission.status = SubmissionStatus.pending
    submission.error_message = None
    submission.error_retryable = True
    submission.completed_at = None
    submission.deduped_from_submission_id = None
    db.add(RoastAttempt(user_id=user.id, submission_id=submission.id))
    db.commit()
    db.refresh(submission)
    logger.info("Submission %d reset for retry", submission.id)
    return submission


def set_visibility(db: Session, user: User, submission_id: int, is_public: bool) -> Submission:
    """Toggle whether the submission's roast is reachable via its public share link."""
    submission = get_owned_submission(db, user, submission_id)
    submission.is_public = is_public
    db.commit()
    db.refresh(submission)
    return submission


def delete_submission(db: Session, user: User, submission_id: int) -> None:
    """Delete an owned submission (analysis and roast cascade)."""
    submission = get_owned_submission(db, user, submission_id)
    db.delete(submission)
    db.commit()
    logger.info("Submission %d deleted", submission_id)


def get_public_roast(db: Session, share_slug: str) -> Submission:
    """Fetch a shared roast by slug with author, analysis and roast loaded.

    Raises:
        NotFoundError: Unknown slug, not public, not completed, or missing roast/analysis.
    """
    submission = db.scalar(
        select(Submission)
        .where(
            Submission.share_slug == share_slug,
            Submission.is_public.is_(True),
            Submission.status == SubmissionStatus.completed,
        )
        .options(
            joinedload(Submission.user),
            joinedload(Submission.analysis),
            joinedload(Submission.roast),
        )
    )
    if submission is None or submission.roast is None or submission.analysis is None:
        raise NotFoundError(NOT_FOUND_MESSAGE)
    return submission
