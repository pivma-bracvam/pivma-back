"""Add optional full name to users.

Revision ID: 7b4f5d6e8a90
Revises: 7a3e1c9b4d82
Create Date: 2026-09-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '7b4f5d6e8a90'
down_revision: str | Sequence[str] | None = '7a3e1c9b4d82'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        'users',
        sa.Column('full_name', sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('users', 'full_name')
