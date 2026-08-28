"""Process participant designations.

Revision ID: 6f2c9a1d4e70
Revises: 5e31a8c7d204
"""

from collections.abc import Sequence
from uuid import UUID

import sqlalchemy as sa
from alembic import op

revision: str = '6f2c9a1d4e70'
down_revision: str | Sequence[str] | None = '5e31a8c7d204'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ADMIN_PROFILE_ID = UUID('00000000-0000-0000-0000-000000000009')
PERMISSION_ID = UUID('00000000-0000-0000-0000-000000000107')
PERMISSION_CODE = 'process.participants.manage'
PERMISSION_DESCRIPTION = 'Gerir participantes e declarações de conflito.'
COMPOSITION_ID = UUID('00000000-0000-0000-0000-000000000207')


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
    op.add_column(
        'assignments', sa.Column('laboratory_id', sa.UUID(), nullable=True)
    )
    op.create_foreign_key(
        'fk_assignments_laboratory_id',
        'assignments',
        'laboratories',
        ['laboratory_id'],
        ['id'],
    )
    op.execute(
        "UPDATE assignments SET role_key = 'proponent' "
        "WHERE role_key = 'PROPONENT'"
    )

    op.create_table(
        'conflict_interest_declarations',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('assignment_id', sa.UUID(), nullable=False),
        sa.Column('has_conflict', sa.Boolean(), nullable=False),
        sa.Column('justification', sa.Text(), nullable=False),
        sa.Column(
            'declared_at',
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        *_audit_columns(),
        sa.ForeignKeyConstraint(
            ['assignment_id'],
            ['assignments.id'],
            name='fk_conflict_declarations_assignment_id',
        ),
    )
    op.create_index(
        'ix_conflict_declarations_assignment_time',
        'conflict_interest_declarations',
        [
            'assignment_id',
            sa.text('declared_at DESC'),
            sa.text('id DESC'),
        ],
    )

    permissions = sa.table(
        'permissions',
        sa.column('id', sa.UUID()),
        sa.column('code'),
        sa.column('description'),
    )
    composition = sa.table(
        'access_profile_permissions',
        sa.column('id', sa.UUID()),
        sa.column('profile_id', sa.UUID()),
        sa.column('permission_id', sa.UUID()),
    )
    op.bulk_insert(
        permissions,
        [
            dict(
                id=PERMISSION_ID,
                code=PERMISSION_CODE,
                description=PERMISSION_DESCRIPTION,
            )
        ],
    )
    op.bulk_insert(
        composition,
        [
            dict(
                id=COMPOSITION_ID,
                profile_id=ADMIN_PROFILE_ID,
                permission_id=PERMISSION_ID,
            )
        ],
    )


def downgrade() -> None:
    op.execute(
        'DELETE FROM access_profile_permissions '
        f"WHERE permission_id = '{PERMISSION_ID}'"
    )
    op.execute(f"DELETE FROM permissions WHERE id = '{PERMISSION_ID}'")

    op.drop_index(
        'ix_conflict_declarations_assignment_time',
        table_name='conflict_interest_declarations',
    )
    op.drop_table('conflict_interest_declarations')

    op.execute(
        "UPDATE assignments SET role_key = 'PROPONENT' "
        "WHERE role_key = 'proponent'"
    )

    op.drop_constraint(
        'fk_assignments_laboratory_id', 'assignments', type_='foreignkey'
    )
    op.drop_column('assignments', 'laboratory_id')
