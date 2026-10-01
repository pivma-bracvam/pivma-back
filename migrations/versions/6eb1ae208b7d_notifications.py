"""Notifications (Spec 036).

Creates the notifications table: the record of each message request and the
work queue read by the notification worker. Existing data is untouched.

Revision ID: 6eb1ae208b7d
Revises: cc6c65843305
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '6eb1ae208b7d'
down_revision: str | Sequence[str] | None = 'cc6c65843305'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PENDING_ONLY = sa.text("status = 'pending' AND deleted_at IS NULL")


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
        'notifications',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('kind', sa.String(64), nullable=False),
        sa.Column('channel', sa.String(16), nullable=False),
        sa.Column('recipient', sa.String(320), nullable=False),
        sa.Column('next_attempt_at', sa.DateTime(), nullable=False),
        sa.Column('payload_encrypted', sa.Text(), nullable=True),
        sa.Column('requested_at', sa.DateTime(), nullable=False),
        sa.Column('subject_type', sa.String(32), nullable=True),
        sa.Column('subject_id', sa.UUID(), nullable=True),
        sa.Column(
            'process_instance_id',
            sa.UUID(),
            sa.ForeignKey(
                'process_instances.id',
                name='fk_notifications_process_instance_id',
            ),
            nullable=True,
        ),
        sa.Column('status', sa.String(16), nullable=False),
        sa.Column('attempts', sa.Integer(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('last_attempt_at', sa.DateTime(), nullable=True),
        sa.Column('sent_at', sa.DateTime(), nullable=True),
        sa.Column('finished_at', sa.DateTime(), nullable=True),
        sa.Column('error_code', sa.String(32), nullable=True),
        sa.Column('error_detail', sa.String(500), nullable=True),
        *_audit_columns('notifications'),
    )
    op.create_index(
        'ix_notifications_pending_due',
        'notifications',
        ['next_attempt_at'],
        postgresql_where=PENDING_ONLY,
    )
    op.create_index(
        'ix_notifications_subject',
        'notifications',
        ['subject_type', 'subject_id'],
    )


def downgrade() -> None:
    op.drop_index('ix_notifications_subject', table_name='notifications')
    op.drop_index('ix_notifications_pending_due', table_name='notifications')
    op.drop_table('notifications')
