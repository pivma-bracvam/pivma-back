"""user_full_name_not_null

Revision ID: 3b75cf649c4e
Revises: 8c5e7a1b9d02
Create Date: 2026-09-04 11:08:01.450180

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3b75cf649c4e'
down_revision: str | Sequence[str] | None = '8c5e7a1b9d02'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        sa.text(
            'UPDATE users SET full_name = username WHERE full_name IS NULL'
        )
    )
    op.alter_column(
        'users',
        'full_name',
        existing_type=sa.String(length=255),
        nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        'users',
        'full_name',
        existing_type=sa.String(length=255),
        nullable=True,
    )

