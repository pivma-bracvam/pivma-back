"""Submission types order and sequential code (Spec 043).

Adds ``process_templates.display_order``, the order declared in each
template YAML for ``GET /processes/templates``, and the
``process_code_sequences`` table, which keeps the last number of the
submission code per year (``VAL-<year>-<n>``). No data migration: the
bootstrap fills the order and the sequence starts empty.

Revision ID: c4e6a8b0d2f1
Revises: a3d5f7b9c1e2
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'c4e6a8b0d2f1'
down_revision: str | Sequence[str] | None = 'a3d5f7b9c1e2'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        'process_templates',
        sa.Column('display_order', sa.Integer(), nullable=True),
    )
    op.create_table(
        'process_code_sequences',
        sa.Column('year', sa.Integer(), primary_key=True),
        sa.Column('last_value', sa.Integer(), nullable=False),
        sa.Column(
            'created_at',
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        *(
            sa.Column(
                column,
                sa.UUID(),
                sa.ForeignKey(
                    'users.id', name=f'fk_process_code_sequences_{column}'
                ),
                nullable=True,
            )
            for column in ('created_by', 'updated_by', 'deleted_by')
        ),
    )


def downgrade() -> None:
    op.drop_table('process_code_sequences')
    op.drop_column('process_templates', 'display_order')
