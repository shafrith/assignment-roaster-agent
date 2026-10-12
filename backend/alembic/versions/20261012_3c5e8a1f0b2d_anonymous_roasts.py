"""anonymous roasts: optional user on submissions and attempts, per-client quota key

- ``submissions.user_id`` and ``roast_attempts.user_id`` become nullable: anonymous (no-login)
  roasts belong to no user and are reached only through their unguessable ``share_slug``.
- ``roast_attempts.client_key``: HMAC of the client IP, counted by the anonymous daily quota.

Revision ID: 3c5e8a1f0b2d
Revises: 7bd88195d9d2
Create Date: 2026-10-12 12:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '3c5e8a1f0b2d'
down_revision: str | None = '7bd88195d9d2'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column('submissions', 'user_id', existing_type=sa.Integer(), nullable=True)
    op.alter_column('roast_attempts', 'user_id', existing_type=sa.Integer(), nullable=True)
    op.add_column('roast_attempts', sa.Column('client_key', sa.String(length=64), nullable=True))
    op.create_index(
        'ix_roast_attempts_client_created',
        'roast_attempts',
        ['client_key', 'created_at'],
        unique=False,
    )


def downgrade() -> None:
    # Anonymous rows have no owner to restore; drop them so NOT NULL can be reinstated.
    op.execute('DELETE FROM roast_attempts WHERE user_id IS NULL')
    op.execute('DELETE FROM submissions WHERE user_id IS NULL')
    op.drop_index('ix_roast_attempts_client_created', table_name='roast_attempts')
    op.drop_column('roast_attempts', 'client_key')
    op.alter_column('roast_attempts', 'user_id', existing_type=sa.Integer(), nullable=False)
    op.alter_column('submissions', 'user_id', existing_type=sa.Integer(), nullable=False)
