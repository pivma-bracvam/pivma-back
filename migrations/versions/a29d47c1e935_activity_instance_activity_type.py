"""Add activity_type to activity_instances.

Revision ID: a29d47c1e935
Revises: e5c2f8a41d90
Create Date: 2026-09-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'a29d47c1e935'
down_revision: str | Sequence[str] | None = 'e5c2f8a41d90'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        'activity_instances',
        sa.Column(
            'activity_type',
            sa.String(length=32),
            nullable=False,
            server_default='form',
        ),
    )


def downgrade() -> None:
    op.drop_column('activity_instances', 'activity_type')
