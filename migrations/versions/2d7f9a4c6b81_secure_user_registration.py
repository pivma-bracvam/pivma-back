"""Secure user registration.

Revision ID: 2d7f9a4c6b81
Revises: b72da3430b3e
Create Date: 2026-08-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '2d7f9a4c6b81'
down_revision: str | Sequence[str] | None = 'b72da3430b3e'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ACTIVE_ONLY = 'deleted_at IS NULL'


def _preflight() -> None:
    connection = op.get_bind()
    username_collisions = connection.scalar(
        sa.text(
            'SELECT count(*) FROM ('
            'SELECT lower(username) FROM users '
            f'WHERE {ACTIVE_ONLY} '
            'GROUP BY lower(username) HAVING count(*) > 1'
            ') AS collisions'
        )
    )
    email_collisions = connection.scalar(
        sa.text(
            'SELECT count(*) FROM ('
            'SELECT lower(email) FROM users '
            f'WHERE {ACTIVE_ONLY} '
            'GROUP BY lower(email) HAVING count(*) > 1'
            ') AS collisions'
        )
    )
    if username_collisions or email_collisions:
        raise RuntimeError(
            'User identifier collisions prevent secure migration'
        )


def upgrade() -> None:
    _preflight()
    op.alter_column('users', 'password', new_column_name='password_hash')
    op.drop_index('ix_uq_users_email_active', table_name='users')
    op.create_index(
        'uq_users_username_ci',
        'users',
        [sa.text('lower(username)')],
        unique=True,
        postgresql_where=sa.text(ACTIVE_ONLY),
    )
    op.create_index(
        'uq_users_email_ci',
        'users',
        [sa.text('lower(email)')],
        unique=True,
        postgresql_where=sa.text(ACTIVE_ONLY),
    )


def downgrade() -> None:
    op.drop_index('uq_users_email_ci', table_name='users')
    op.drop_index('uq_users_username_ci', table_name='users')
    op.create_index(
        'ix_uq_users_email_active',
        'users',
        ['email'],
        unique=True,
        postgresql_where=sa.text(ACTIVE_ONLY),
    )
    op.alter_column(
        'users', 'password_hash', new_column_name='password'
    )
