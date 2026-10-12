"""roast attempts, retry tracking, refresh-token grace window, query-matched indexes

- ``roast_attempts``: one row per pipeline run (first attempt or retry), counted by the daily
  quota (SEC-2). Backfilled with one attempt per existing submission so quota usage is
  unchanged across the deploy.
- ``submissions.error_retryable``: False for deterministic failures (SEC-2).
- ``submissions.deduped_from_submission_id``: provenance of copied roasts (COR-7).
- ``roasts.prompt_version``: part of the dedupe key; NULL (never reused) for older roasts.
- ``refresh_tokens.revoked_at`` / ``replaced_by_id``: rotation grace window (COR-5).
- Indexes matching the real queries (PERF-4): functional, partial dedupe index and
  ``(user_id, created_at)``; the unused composite and the now-redundant ``user_id`` index go.

Revision ID: 7bd88195d9d2
Revises: 9da6dee9622e
Create Date: 2026-10-12 09:41:15.501373

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '7bd88195d9d2'
down_revision: str | None = '9da6dee9622e'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'roast_attempts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('submission_id', sa.Integer(), nullable=True),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ['submission_id'],
            ['submissions.id'],
            name=op.f('fk_roast_attempts_submission_id_submissions'),
            ondelete='SET NULL',
        ),
        sa.ForeignKeyConstraint(
            ['user_id'],
            ['users.id'],
            name=op.f('fk_roast_attempts_user_id_users'),
            ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_roast_attempts')),
    )
    op.create_index(
        op.f('ix_roast_attempts_submission_id'), 'roast_attempts', ['submission_id'], unique=False
    )
    op.create_index(
        'ix_roast_attempts_user_created', 'roast_attempts', ['user_id', 'created_at'], unique=False
    )
    # Backfill: every existing submission was one attempt at its creation time.
    op.execute(
        "INSERT INTO roast_attempts (user_id, submission_id, created_at) "
        "SELECT user_id, id, created_at FROM submissions"
    )

    op.add_column(
        'refresh_tokens', sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column('refresh_tokens', sa.Column('replaced_by_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        op.f('fk_refresh_tokens_replaced_by_id_refresh_tokens'),
        'refresh_tokens',
        'refresh_tokens',
        ['replaced_by_id'],
        ['id'],
        ondelete='SET NULL',
    )

    op.add_column(
        'submissions',
        sa.Column(
            'error_retryable', sa.Boolean(), server_default=sa.text('true'), nullable=False
        ),
    )
    op.add_column(
        'submissions', sa.Column('deduped_from_submission_id', sa.Integer(), nullable=True)
    )
    op.create_foreign_key(
        op.f('fk_submissions_deduped_from_submission_id_submissions'),
        'submissions',
        'submissions',
        ['deduped_from_submission_id'],
        ['id'],
        ondelete='SET NULL',
    )

    op.add_column('roasts', sa.Column('prompt_version', sa.String(length=40), nullable=True))

    op.drop_index(op.f('ix_submissions_repo_owner_name_sha'), table_name='submissions')
    op.drop_index(op.f('ix_submissions_user_id'), table_name='submissions')
    op.create_index(
        'ix_submissions_dedupe',
        'submissions',
        [
            'commit_sha',
            sa.literal_column('lower(repo_owner)'),
            sa.literal_column('lower(repo_name)'),
        ],
        unique=False,
        postgresql_where=sa.text("status = 'completed'"),
    )
    op.create_index(
        'ix_submissions_user_created', 'submissions', ['user_id', 'created_at'], unique=False
    )


def downgrade() -> None:
    op.drop_index('ix_submissions_user_created', table_name='submissions')
    op.drop_index(
        'ix_submissions_dedupe',
        table_name='submissions',
        postgresql_where=sa.text("status = 'completed'"),
    )
    op.create_index(op.f('ix_submissions_user_id'), 'submissions', ['user_id'], unique=False)
    op.create_index(
        op.f('ix_submissions_repo_owner_name_sha'),
        'submissions',
        ['repo_owner', 'repo_name', 'commit_sha'],
        unique=False,
    )

    op.drop_column('roasts', 'prompt_version')

    op.drop_constraint(
        op.f('fk_submissions_deduped_from_submission_id_submissions'),
        'submissions',
        type_='foreignkey',
    )
    op.drop_column('submissions', 'deduped_from_submission_id')
    op.drop_column('submissions', 'error_retryable')

    op.drop_constraint(
        op.f('fk_refresh_tokens_replaced_by_id_refresh_tokens'),
        'refresh_tokens',
        type_='foreignkey',
    )
    op.drop_column('refresh_tokens', 'replaced_by_id')
    op.drop_column('refresh_tokens', 'revoked_at')

    op.drop_index('ix_roast_attempts_user_created', table_name='roast_attempts')
    op.drop_index(op.f('ix_roast_attempts_submission_id'), table_name='roast_attempts')
    op.drop_table('roast_attempts')
