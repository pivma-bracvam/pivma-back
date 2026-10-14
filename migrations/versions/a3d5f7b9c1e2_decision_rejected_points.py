"""Rejected points on decisions (Spec 042, issue #27).

Adds ``decisions.rejected_points``, the list of ``{activity_key, reason}``
recorded when BraCVAM rejects the study structure (research R5). Every other
decision, including the existing ones, keeps the column empty.

Revision ID: a3d5f7b9c1e2
Revises: e8a4c2f61b37
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = 'a3d5f7b9c1e2'
down_revision: str | Sequence[str] | None = 'e8a4c2f61b37'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        'decisions',
        sa.Column('rejected_points', JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('decisions', 'rejected_points')
