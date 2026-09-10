"""evaluation_run_content_snapshot

Revision ID: e5c2f8a41d90
Revises: d3f9a1c47b28
Create Date: 2026-09-10

Spec 014 — snapshot imutável do conteúdo avaliado por execução de
pré-avaliação (`evaluation_runs.evaluated_content_snapshot`, JSONB nullable).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = 'e5c2f8a41d90'
down_revision: str | Sequence[str] | None = 'd3f9a1c47b28'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        'evaluation_runs',
        sa.Column(
            'evaluated_content_snapshot',
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column('evaluation_runs', 'evaluated_content_snapshot')
