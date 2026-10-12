"""Submission pipeline: fetch repo metadata, analyze, roast, and persist results.

``run_pipeline`` runs as a FastAPI ``BackgroundTask`` and therefore opens its own DB session and
never raises. Each status change is committed so polling clients can follow progress.

Concurrency and robustness:

- A process-wide semaphore (``MAX_CONCURRENT_ROASTS``) bounds how many pipelines hit GitHub and
  the LLM at once; queued submissions simply stay ``pending`` (PERF-2).
- Every status change is a compare-and-set ``UPDATE ... WHERE status IN (...)``, so a duplicate
  run, a sweep, or a retry can never be overwritten by a stale writer (COR-3).
- A running pipeline is bounded by :data:`PIPELINE_TIMEOUT_SECONDS`. Background tasks die with
  the process, so at startup every non-terminal submission is failed, and a periodic sweep
  fails orphans older than :data:`STALE_SUBMISSION_MINUTES` (COR-2).
"""

import asyncio
import logging
import weakref
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import CursorResult, func, select, update
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.models.repo_analysis import RepoAnalysis
from app.models.roast import Roast
from app.models.submission import Submission, SubmissionStatus
from app.services.contracts import PipelineError
from app.services.github_client import GitHubClient
from app.services.prompts import PROMPT_VERSION
from app.services.repo_analyzer import analyze_repo
from app.services.roast_engine import generate_roast

logger = logging.getLogger(__name__)

# A pipeline that has started running is cancelled after this long (GitHub fetches + LLM).
PIPELINE_TIMEOUT_SECONDS = 10 * 60
# Non-terminal submissions untouched for longer than this are orphans (> pipeline timeout).
STALE_SUBMISSION_MINUTES = 12
STALE_SWEEP_INTERVAL_SECONDS = 60
ERROR_MESSAGE_MAX_LENGTH = 500
GENERIC_FAILURE_MESSAGE = "Edho thappa poiduchu machan, konjam neram kazhichu retry pannu 🙏"
STALE_FAILURE_MESSAGE = "Server restart aagiduchu, roast paadhila nikkuthu. Retry pannu machan 🔁"
TIMEOUT_FAILURE_MESSAGE = "Roast romba neram eduthuchu machan, timeout aagiduchu. Retry pannu ⏳"

NON_TERMINAL_STATUSES: tuple[SubmissionStatus, ...] = (
    SubmissionStatus.pending,
    SubmissionStatus.analyzing,
    SubmissionStatus.roasting,
)

_NON_COPYABLE_COLUMNS = frozenset({"id", "submission_id", "created_at"})

# Submission ids queued or running in THIS process; the periodic sweep never fails them.
_in_flight: set[int] = set()
# One semaphore per event loop (an asyncio.Semaphore binds to the loop that first waits on it).
_semaphores: "weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, asyncio.Semaphore]" = (
    weakref.WeakKeyDictionary()
)


class _Superseded(Exception):
    """The submission left the expected state (swept, deleted, or handled by another run)."""


def _pipeline_semaphore() -> asyncio.Semaphore:
    """Return the running loop's pipeline semaphore (``MAX_CONCURRENT_ROASTS`` slots)."""
    loop = asyncio.get_running_loop()
    semaphore = _semaphores.get(loop)
    if semaphore is None:
        semaphore = asyncio.Semaphore(settings.MAX_CONCURRENT_ROASTS)
        _semaphores[loop] = semaphore
    return semaphore


def _copyable_values(row: RepoAnalysis | Roast) -> dict[str, Any]:
    """Return a row's column values minus identity/ownership/timestamp columns."""
    return {
        column.key: getattr(row, column.key)
        for column in row.__table__.columns
        if column.key not in _NON_COPYABLE_COLUMNS
    }


def _transition(
    db: Session,
    submission_id: int,
    expected: Iterable[SubmissionStatus],
    **values: Any,
) -> bool:
    """Compare-and-set the submission's columns while its status is one of ``expected``.

    Does not commit. Returns:
        True when the row was updated, False when its status no longer matches.
    """
    result = db.execute(
        update(Submission)
        .where(Submission.id == submission_id, Submission.status.in_(list(expected)))
        .values(**values)
        .returning(Submission.id)
        .execution_options(synchronize_session="fetch")
    )
    return result.first() is not None


def _advance(
    db: Session, submission_id: int, expected: SubmissionStatus, new: SubmissionStatus
) -> None:
    """Move ``expected`` -> ``new`` and commit, or roll back and raise :class:`_Superseded`."""
    if not _transition(db, submission_id, [expected], status=new):
        db.rollback()
        raise _Superseded
    db.commit()


def _find_dedupe_source(db: Session, submission: Submission) -> Submission | None:
    """Find another completed submission of the same repo at the same commit that has a roast
    generated with the current :data:`PROMPT_VERSION` (older prompts are never reused).

    Matches ``ix_submissions_dedupe`` (commit sha, lower(owner), lower(name), completed).
    """
    if not submission.commit_sha:
        return None
    return db.scalar(
        select(Submission)
        .join(Roast, Roast.submission_id == Submission.id)
        .join(RepoAnalysis, RepoAnalysis.submission_id == Submission.id)
        .where(
            Submission.id != submission.id,
            Submission.status == SubmissionStatus.completed,
            Submission.commit_sha == submission.commit_sha,
            Roast.prompt_version == PROMPT_VERSION,
            func.lower(Submission.repo_owner) == submission.repo_owner.lower(),
            func.lower(Submission.repo_name) == submission.repo_name.lower(),
        )
        .order_by(Submission.completed_at.desc())
        .limit(1)
    )


def _complete(db: Session, submission_id: int, **extra: Any) -> None:
    """Mark the submission completed (with any pending inserts) and commit.

    Raises:
        _Superseded: The submission is no longer in progress; pending inserts are discarded.
    """
    if not _transition(
        db,
        submission_id,
        [SubmissionStatus.analyzing, SubmissionStatus.roasting],
        status=SubmissionStatus.completed,
        error_message=None,
        completed_at=datetime.now(UTC),
        **extra,
    ):
        db.rollback()
        raise _Superseded
    db.commit()


def _mark_failed(submission_id: int, message: str, retryable: bool = True) -> None:
    """Mark an in-progress submission failed in a fresh session. Never raises.

    Completed or already-failed submissions are left untouched.

    Args:
        submission_id: Submission to fail.
        message: User-safe (Tanglish) error message.
        retryable: False for deterministic failures; retry is then refused.
    """
    try:
        with SessionLocal() as db:
            _transition(
                db,
                submission_id,
                NON_TERMINAL_STATUSES,
                status=SubmissionStatus.failed,
                error_message=message[:ERROR_MESSAGE_MAX_LENGTH],
                error_retryable=retryable,
            )
            db.commit()
    except Exception:
        logger.exception("Could not mark submission %d as failed", submission_id)


async def _run(db: Session, submission_id: int) -> None:
    """Pipeline body. Raises on failure; ``run_pipeline`` handles errors."""
    submission = db.get(Submission, submission_id)
    if submission is None:
        logger.warning("Pipeline: submission %d not found (deleted?)", submission_id)
        return
    if submission.status != SubmissionStatus.pending:
        logger.warning(
            "Pipeline: submission %d is %s, not pending; skipping", submission_id, submission.status
        )
        return

    _advance(db, submission_id, SubmissionStatus.pending, SubmissionStatus.analyzing)

    async with GitHubClient() as gh:
        info = await gh.get_repo_info(submission.repo_owner, submission.repo_name)
        submission.default_branch = info.default_branch
        submission.commit_sha = info.head_sha
        db.commit()

        source = _find_dedupe_source(db, submission)
        if source is not None and source.analysis is not None and source.roast is not None:
            db.add(RepoAnalysis(submission_id=submission_id, **_copyable_values(source.analysis)))
            roast_values = _copyable_values(source.roast)
            # No tokens were spent on the copy; keep cost reporting honest (COR-7).
            roast_values.update(input_tokens=0, output_tokens=0)
            db.add(Roast(submission_id=submission_id, **roast_values))
            _complete(db, submission_id, deduped_from_submission_id=source.id)
            logger.info(
                "Pipeline: submission %d deduped from submission %d", submission_id, source.id
            )
            return

        analysis = await analyze_repo(gh, info)

    db.add(RepoAnalysis(submission_id=submission_id, **analysis.to_model_kwargs()))
    _advance(db, submission_id, SubmissionStatus.analyzing, SubmissionStatus.roasting)

    roast = await generate_roast(info, analysis)
    db.add(
        Roast(
            submission_id=submission_id,
            prompt_version=PROMPT_VERSION,
            **roast.to_model_kwargs(),
        )
    )
    _complete(db, submission_id)
    logger.info("Pipeline: submission %d completed", submission_id)


async def _run_guarded(submission_id: int) -> None:
    """Run the pipeline under its timeout, converting every failure into a ``failed`` row."""
    try:
        async with asyncio.timeout(PIPELINE_TIMEOUT_SECONDS):
            with SessionLocal() as db:
                try:
                    await _run(db, submission_id)
                except BaseException:
                    db.rollback()
                    raise
    except _Superseded:
        logger.info("Pipeline: submission %d changed state elsewhere; stopping", submission_id)
    except PipelineError as exc:
        logger.info("Pipeline: submission %d failed: %s", submission_id, type(exc).__name__)
        _mark_failed(submission_id, exc.detail, retryable=exc.retryable)
    except TimeoutError:
        logger.warning("Pipeline: submission %d timed out", submission_id)
        _mark_failed(submission_id, TIMEOUT_FAILURE_MESSAGE)
    except Exception:
        logger.exception("Pipeline: unexpected error for submission %d", submission_id)
        _mark_failed(submission_id, GENERIC_FAILURE_MESSAGE)


async def run_pipeline(submission_id: int) -> None:
    """Analyze and roast a submission. Runs as a background task and never raises.

    Waits for a free slot of the process-wide ``MAX_CONCURRENT_ROASTS`` semaphore (the
    submission stays ``pending`` meanwhile). Expected failures (:class:`PipelineError`) store
    their user-safe ``detail`` and retryability; anything else stores a generic message and is
    logged with the submission id only.

    Args:
        submission_id: Id of a ``pending`` submission.
    """
    _in_flight.add(submission_id)
    try:
        async with _pipeline_semaphore():
            await _run_guarded(submission_id)
    finally:
        _in_flight.discard(submission_id)


def fail_stale_submissions(
    max_age: timedelta | None = timedelta(minutes=STALE_SUBMISSION_MINUTES),
) -> int:
    """Mark orphaned ``pending``/``analyzing``/``roasting`` submissions as (retryable) ``failed``.

    Background tasks are lost when the process stops. At startup no task of this process can
    exist yet, so ``max_age=None`` fails every non-terminal submission (single-process MVP).
    The periodic sweep uses the default age cutoff and skips submissions queued or running in
    this process.

    Args:
        max_age: Only fail rows whose ``updated_at`` is older than this; None fails all.

    Returns:
        The number of submissions marked as failed.
    """
    conditions: list[Any] = [Submission.status.in_(NON_TERMINAL_STATUSES)]
    if max_age is not None:
        conditions.append(Submission.updated_at < datetime.now(UTC) - max_age)
    in_flight = list(_in_flight)
    if in_flight:
        conditions.append(Submission.id.not_in(in_flight))
    with SessionLocal() as db:
        result: CursorResult[Any] = db.execute(  # type: ignore[assignment]
            update(Submission)
            .where(*conditions)
            .values(
                status=SubmissionStatus.failed,
                error_message=STALE_FAILURE_MESSAGE,
                error_retryable=True,
            )
            .execution_options(synchronize_session=False)
        )
        db.commit()
        return int(result.rowcount or 0)


async def sweep_stale_submissions_forever(
    interval_seconds: float = STALE_SWEEP_INTERVAL_SECONDS,
) -> None:
    """Periodically fail orphaned submissions until cancelled. Never raises (except cancel).

    Args:
        interval_seconds: Delay between sweeps.
    """
    while True:
        await asyncio.sleep(interval_seconds)
        try:
            failed = await asyncio.to_thread(fail_stale_submissions)
        except Exception:
            logger.exception("Periodic stale-submission sweep failed")
            continue
        if failed:
            logger.info("Periodic sweep marked %d stale submissions as failed", failed)
