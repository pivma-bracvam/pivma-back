"""Guidance to the laboratory on a nonconformity decision (Spec 040, FR-047).

Adds the nullable lab_guidance column to sample_receipt_nonconformities.
Existing decisions keep it empty.

Revision ID: b7c3e1f2a9d4
Revises: 9d4e2b7a1c30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'b7c3e1f2a9d4'
down_revision: str | Sequence[str] | None = '9d4e2b7a1c30'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = 'sample_receipt_nonconformities'


def upgrade() -> None:
    op.add_column(TABLE, sa.Column('lab_guidance', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column(TABLE, 'lab_guidance')
