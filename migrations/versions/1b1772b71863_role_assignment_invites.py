"""Role assignment invites (Spec 028).

Revision ID: 1b1772b71863
Revises: fa506675d3f9
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '1b1772b71863'
down_revision: str | Sequence[str] | None = 'fa506675d3f9'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PENDING_ONLY = sa.text("status = 'pending' AND deleted_at IS NULL")


def _audit_columns() -> list[sa.Column]:
    return [
        sa.Column(
            'created_at',
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column(
            'created_by',
            sa.UUID(),
            sa.ForeignKey('users.id', use_alter=True),
            nullable=True,
        ),
        sa.Column(
            'updated_by',
            sa.UUID(),
            sa.ForeignKey('users.id', use_alter=True),
            nullable=True,
        ),
        sa.Column(
            'deleted_by',
            sa.UUID(),
            sa.ForeignKey('users.id', use_alter=True),
            nullable=True,
        ),
    ]


def upgrade() -> None:
    op.create_table(
        'role_assignment_invites',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('process_instance_id', sa.UUID(), nullable=False),
        sa.Column('role_key', sa.String(64), nullable=False),
        sa.Column('laboratory_id', sa.UUID(), nullable=True),
        sa.Column('email', sa.String(320), nullable=False),
        sa.Column(
            'channel',
            sa.String(32),
            nullable=False,
            server_default='link',
        ),
        sa.Column('token_hash', sa.String(64), nullable=False),
        sa.Column(
            'status',
            sa.String(16),
            nullable=False,
            server_default='pending',
        ),
        sa.Column(
            'expires_at', sa.DateTime(), nullable=False
        ),
        sa.Column(
            'accepted_at', sa.DateTime(), nullable=True
        ),
        sa.Column('accepted_by', sa.UUID(), nullable=True),
        sa.Column(
            'revoked_at', sa.DateTime(), nullable=True
        ),
        sa.Column('revoked_by', sa.UUID(), nullable=True),
        *_audit_columns(),
        sa.ForeignKeyConstraint(
            ['process_instance_id'],
            ['process_instances.id'],
            name='fk_role_assignment_invites_process_instance_id',
        ),
        sa.ForeignKeyConstraint(
            ['laboratory_id'],
            ['laboratories.id'],
            name='fk_role_assignment_invites_laboratory_id',
        ),
        sa.ForeignKeyConstraint(
            ['accepted_by'],
            ['users.id'],
            name='fk_role_assignment_invites_accepted_by',
        ),
        sa.ForeignKeyConstraint(
            ['revoked_by'],
            ['users.id'],
            name='fk_role_assignment_invites_revoked_by',
        ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'uq_role_assignment_invites_pending',
        'role_assignment_invites',
        ['process_instance_id', 'role_key', 'email'],
        unique=True,
        postgresql_where=PENDING_ONLY,
    )
    op.create_index(
        'uq_role_assignment_invites_token_hash',
        'role_assignment_invites',
        ['token_hash'],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        'uq_role_assignment_invites_token_hash',
        table_name='role_assignment_invites',
    )
    op.drop_index(
        'uq_role_assignment_invites_pending',
        table_name='role_assignment_invites',
    )
    op.drop_table('role_assignment_invites')
