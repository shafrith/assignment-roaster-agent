"""Submission business logic: create, fetch by share slug, retry, public share.

There is no login: a submission is reached only through its unguessable ``share_slug``, and
every pipeline attempt is charged to a per-client quota key (an HMAC of the client IP, see
:func:`app.rate_limit.client_quota_key`).
"""

import logging
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload, selectinload

from app.config import settings
from app.exceptions import ConflictError, NotFoundError, RateLimitedError
from app.models.roast_attempt import RoastAttempt
from app.models.submission import Submission, SubmissionStatus
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


def _lock_client(db: Session, client_key: str) -> None:
    """Take a transaction-scoped advisory lock on the client's quota key.

    Serializes quota check + attempt insert per client, so concurrent requests (several
    workers, or threadpool routes) cannot both pass the check (COR-3).
    """
    db.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"), {"key": client_key})


def attempts_used_today(db: Session, client_key: str) -> int:
    """Return the client's pipeline attempts (creates + retries) in the last 24 hours.

    Args:
        db: Database session.
        client_key: Hashed client identifier from :func:`app.rate_limit.client_quota_key`.

    Returns:
        Attempts charged against the client's daily quota.
    """
    since = datetime.now(UTC) - QUOTA_WINDOW
    count = db.scalar(
        select(func.count(RoastAttempt.id)).where(
            RoastAttempt.client_key == client_key, RoastAttempt.created_at >= since
        )
    )
    return int(count or 0)


def _enforce_daily_limit(db: Session, client_key: str) -> None:
    """Raise when the client already used ``ROAST_DAILY_LIMIT`` attempts in the last 24h.

    Must be called after :func:`_lock_client` in the same transaction.

    Raises:
        RateLimitedError: Quota exhausted.
    """
    if attempts_used_today(db, client_key) >= settings.ROAST_DAILY_LIMIT:
        raise RateLimitedError(DAILY_LIMIT_MESSAGE)


def create_submission(db: Session, client_key: str, repo_url: str) -> Submission:
    """Validate the repo URL, enforce the client's daily quota, and insert a pending submission.

    Roasts are always public: whoever holds the share link can view them. The quota check,
    the submission insert and its :class:`RoastAttempt` are one transaction holding the
    client's advisory lock.

    Args:
        db: Request DB session.
        client_key: Hashed client identifier charged for the attempt.
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
        _lock_client(db, client_key)
        try:
            _enforce_daily_limit(db, client_key)
        except RateLimitedError:
            db.rollback()
            raise
        submission = Submission(
            repo_url=normalized_url,
            repo_owner=owner,
            repo_name=repo,
            status=SubmissionStatus.pending,
            is_public=True,
            share_slug=_generate_share_slug(),
        )
        db.add(submission)
        try:
            db.flush()
            db.add(RoastAttempt(client_key=client_key, submission_id=submission.id))
            db.commit()
        except IntegrityError:
            db.rollback()
            if attempt == SLUG_MAX_ATTEMPTS:
                raise
            logger.warning("Share slug collision on attempt %d; retrying", attempt)
            continue
        db.refresh(submission)
        logger.info("Submission %d created", submission.id)
        return submission
    raise RuntimeError("unreachable")  # pragma: no cover


def get_roast_by_slug(db: Session, share_slug: str) -> Submission:
    """Fetch a public roast in any status by share slug, for the result page.

    Raises:
        NotFoundError: Unknown slug or not public (existence is not leaked).
    """
    submission = db.scalar(
        select(Submission)
        .where(Submission.share_slug == share_slug, Submission.is_public.is_(True))
        .options(selectinload(Submission.analysis), selectinload(Submission.roast))
    )
    if submission is None:
        raise NotFoundError(NOT_FOUND_MESSAGE)
    return submission


def _check_retryable(db: Session, submission: Submission) -> None:
    """Raise unless the (row-locked) submission may be retried.

    Raises:
        ConflictError: Not ``failed``, not retryable, or the retry cap is reached.
    """
    if submission.status != SubmissionStatus.failed:
        raise ConflictError(RETRY_CONFLICT_MESSAGE)
    if not submission.error_retryable:
        raise ConflictError(RETRY_NOT_RETRYABLE_MESSAGE)
    attempts = db.scalar(
        select(func.count(RoastAttempt.id)).where(RoastAttempt.submission_id == submission.id)
    )
    if int(attempts or 0) > settings.ROAST_MAX_RETRIES:
        raise ConflictError(RETRY_LIMIT_MESSAGE)


def retry_submission(db: Session, client_key: str, share_slug: str) -> Submission:
    """Reset a ``failed`` submission to ``pending`` so the pipeline can run again.

    Every retry is a new :class:`RoastAttempt` charged to the caller: it counts toward their
    daily quota, and a submission gets at most ``ROAST_MAX_RETRIES`` retries. Deterministic
    failures (private or missing repo, repo too large) are not retryable. Stale partial
    ``RepoAnalysis`` / ``Roast`` rows are deleted. Check and update run under the client's
    advisory lock and the submission row lock.

    Raises:
        NotFoundError: Unknown slug or not public.
        ConflictError: Not ``failed``, not retryable, or the retry cap is reached.
        RateLimitedError: Daily quota exhausted.
    """
    _lock_client(db, client_key)
    try:
        submission = db.scalar(
            select(Submission)
            .where(Submission.share_slug == share_slug, Submission.is_public.is_(True))
            .with_for_update()
            # The locked row may be newer than an identity-map copy loaded earlier.
            .execution_options(populate_existing=True)
        )
        if submission is None:
            raise NotFoundError(NOT_FOUND_MESSAGE)
        _check_retryable(db, submission)
        _enforce_daily_limit(db, client_key)
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
    db.add(RoastAttempt(client_key=client_key, submission_id=submission.id))
    db.commit()
    db.refresh(submission)
    logger.info("Submission %d reset for retry", submission.id)
    return submission


def get_public_roast(db: Session, share_slug: str) -> Submission:
    """Fetch a shared roast by slug with analysis and roast loaded.

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
        .options(joinedload(Submission.analysis), joinedload(Submission.roast))
    )
    if submission is None or submission.roast is None or submission.analysis is None:
        raise NotFoundError(NOT_FOUND_MESSAGE)
    return submission
