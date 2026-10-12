"""drop login: users, refresh tokens and every user_id column

The app no longer has accounts: roasts are reached by share slug and quota is charged per
client key. Legacy private roasts keep ``is_public = false`` and stay hidden.

Downgrade recreates the empty tables and nullable ``user_id`` columns; dropped account data is
not restored.

Revision ID: 8f41d2b7c6a9
Revises: 3c5e8a1f0b2d
Create Date: 2026-10-12 13:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '8f41d2b7c6a9'
down_revision: str | None = '3c5e8a1f0b2d'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Dropping a column also drops its foreign key and the indexes that cover it.
    op.drop_column('roast_attempts', 'user_id')
    op.drop_column('submissions', 'user_id')
    op.drop_table('refresh_tokens')
    op.drop_table('users')


def downgrade() -> None:
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('github_id', sa.BigInteger(), nullable=False),
        sa.Column('github_username', sa.String(length=100), nullable=False),
        sa.Column('display_name', sa.String(length=200), nullable=True),
        sa.Column('avatar_url', sa.String(length=500), nullable=True),
        sa.Column('email', sa.String(length=255), nullable=True),
        sa.Column(
            'default_roast_public', sa.Boolean(), server_default=sa.text('true'), nullable=False
        ),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('is_admin', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_users')),
    )
    op.create_index(op.f('ix_users_github_id'), 'users', ['github_id'], unique=True)
    op.create_table(
        'refresh_tokens',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('token_hash', sa.String(length=128), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('revoked', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('replaced_by_id', sa.Integer(), nullable=True),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ['user_id'],
            ['users.id'],
            name=op.f('fk_refresh_tokens_user_id_users'),
            ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['replaced_by_id'],
            ['refresh_tokens.id'],
            name=op.f('fk_refresh_tokens_replaced_by_id_refresh_tokens'),
            ondelete='SET NULL',
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_refresh_tokens')),
        sa.UniqueConstraint('token_hash', name=op.f('uq_refresh_tokens_token_hash')),
    )
    op.create_index(op.f('ix_refresh_tokens_user_id'), 'refresh_tokens', ['user_id'], unique=False)
    for table in ('submissions', 'roast_attempts'):
        op.add_column(table, sa.Column('user_id', sa.Integer(), nullable=True))
        op.create_foreign_key(
            op.f(f'fk_{table}_user_id_users'),
            table,
            'users',
            ['user_id'],
            ['id'],
            ondelete='CASCADE',
        )
    op.create_index(
        'ix_submissions_user_created', 'submissions', ['user_id', 'created_at'], unique=False
    )
    op.create_index(
        'ix_roast_attempts_user_created', 'roast_attempts', ['user_id', 'created_at'], unique=False
    )
