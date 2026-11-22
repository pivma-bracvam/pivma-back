"""Alerts (Spec 047).

Creates the alerts table: the in-app notices of each user, with the target
the frontend uses to build the route and the read state. Existing data is
untouched.

Revision ID: b7d3e9a1c5f2
Revises: c4e6a8b0d2f1
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = 'b7d3e9a1c5f2'
down_revision: str | Sequence[str] | None = 'c4e6a8b0d2f1'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _audit_columns(table: str) -> list[sa.Column]:
    return [
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
                sa.ForeignKey('users.id', name=f'fk_{table}_{column}'),
                nullable=True,
            )
            for column in ('created_by', 'updated_by', 'deleted_by')
        ),
    ]


def upgrade() -> None:
    op.create_table(
        'alerts',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column(
            'user_id',
            sa.UUID(),
            sa.ForeignKey('users.id', name='fk_alerts_user_id'),
            nullable=False,
        ),
        sa.Column('kind', sa.String(64), nullable=False),
        sa.Column('target_type', sa.String(32), nullable=False),
        sa.Column(
            'process_instance_id',
            sa.UUID(),
            sa.ForeignKey(
                'process_instances.id',
                name='fk_alerts_process_instance_id',
            ),
            nullable=False,
        ),
        sa.Column('target_id', sa.UUID(), nullable=True),
        sa.Column(
            'params', postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column('read_at', sa.DateTime(), nullable=True),
        *_audit_columns('alerts'),
        sa.CheckConstraint(
            "(target_type = 'process') = (target_id IS NULL)",
            name='ck_alerts_target_id_by_type',
        ),
    )
    op.create_index(
        'ix_alerts_user_created',
        'alerts',
        ['user_id', sa.text('created_at DESC')],
    )
    op.create_index(
        'ix_alerts_user_unread',
        'alerts',
        ['user_id'],
        postgresql_where=sa.text('read_at IS NULL'),
    )


def downgrade() -> None:
    op.drop_index('ix_alerts_user_unread', table_name='alerts')
    op.drop_index('ix_alerts_user_created', table_name='alerts')
    op.drop_table('alerts')
