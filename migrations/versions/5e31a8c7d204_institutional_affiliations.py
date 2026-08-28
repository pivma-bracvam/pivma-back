"""Institutional affiliations.

Revision ID: 5e31a8c7d204
Revises: 1bd1b3d5ddad
"""

from collections.abc import Sequence
from uuid import UUID

import sqlalchemy as sa
from alembic import op

revision: str = '5e31a8c7d204'
down_revision: str | Sequence[str] | None = '1bd1b3d5ddad'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ACTIVE_ONLY = sa.text('deleted_at IS NULL')
ADMIN_PROFILE_ID = UUID('00000000-0000-0000-0000-000000000009')
PERMISSIONS = (
    (
        UUID('00000000-0000-0000-0000-000000000104'),
        'institutional.read',
        'Consultar dados institucionais.',
    ),
    (
        UUID('00000000-0000-0000-0000-000000000105'),
        'institutional.catalogs.manage',
        'Gerir catálogos institucionais.',
    ),
    (
        UUID('00000000-0000-0000-0000-000000000106'),
        'institutional.affiliations.manage',
        'Gerir vínculos institucionais.',
    ),
)


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
        'institutions',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        *_audit_columns(),
    )
    op.create_index(
        'uq_institutions_name_ci_active',
        'institutions',
        [sa.text('lower(name)')],
        unique=True,
        postgresql_where=ACTIVE_ONLY,
    )
    op.create_index(
        'ix_institutions_name_id',
        'institutions',
        [sa.text('lower(name)'), 'id'],
    )

    op.create_table(
        'laboratories',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('institution_id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        *_audit_columns(),
        sa.ForeignKeyConstraint(['institution_id'], ['institutions.id']),
        sa.UniqueConstraint(
            'id', 'institution_id', name='uq_laboratories_id_institution_id'
        ),
    )
    op.create_index(
        'uq_laboratories_institution_name_ci_active',
        'laboratories',
        ['institution_id', sa.text('lower(name)')],
        unique=True,
        postgresql_where=ACTIVE_ONLY,
    )
    op.create_index(
        'ix_laboratories_institution_name_id',
        'laboratories',
        ['institution_id', sa.text('lower(name)'), 'id'],
    )

    op.create_table(
        'user_institutional_affiliations',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('institution_id', sa.UUID(), nullable=False),
        sa.Column('laboratory_id', sa.UUID(), nullable=True),
        *_audit_columns(),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['institution_id'], ['institutions.id']),
        sa.ForeignKeyConstraint(
            ['laboratory_id', 'institution_id'],
            ['laboratories.id', 'laboratories.institution_id'],
            name='fk_affiliations_laboratory_institution',
        ),
    )
    op.create_index(
        'uq_affiliations_active_institution',
        'user_institutional_affiliations',
        ['user_id', 'institution_id'],
        unique=True,
        postgresql_where=sa.text(
            'deleted_at IS NULL AND laboratory_id IS NULL'
        ),
    )
    op.create_index(
        'uq_affiliations_active_laboratory',
        'user_institutional_affiliations',
        ['user_id', 'institution_id', 'laboratory_id'],
        unique=True,
        postgresql_where=sa.text(
            'deleted_at IS NULL AND laboratory_id IS NOT NULL'
        ),
    )
    op.create_index(
        'ix_affiliations_active_scope',
        'user_institutional_affiliations',
        ['user_id', 'institution_id', 'laboratory_id'],
        postgresql_where=ACTIVE_ONLY,
    )

    op.create_table(
        'institutional_changes',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('action', sa.String(64), nullable=False),
        sa.Column('target_type', sa.String(32), nullable=False),
        sa.Column('target_id', sa.UUID(), nullable=False),
        *_audit_columns(),
    )
    op.create_index(
        'ix_institutional_changes_created_at_id_desc',
        'institutional_changes',
        [sa.text('created_at DESC'), sa.text('id DESC')],
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
            dict(id=permission_id, code=code, description=description)
            for permission_id, code, description in PERMISSIONS
        ],
    )
    op.bulk_insert(
        composition,
        [
            dict(
                id=UUID(f'00000000-0000-0000-0000-00000000020{i}'),
                profile_id=ADMIN_PROFILE_ID,
                permission_id=permission_id,
            )
            for i, (permission_id, _, _) in enumerate(PERMISSIONS, 4)
        ],
    )


def downgrade() -> None:
    permission_ids = tuple(
        str(permission_id) for permission_id, _, _ in PERMISSIONS
    )
    op.execute(
        sa
        .text(
            'DELETE FROM access_profile_permissions '
            'WHERE permission_id IN :permission_ids'
        )
        .bindparams(sa.bindparam('permission_ids', expanding=True))
        .bindparams(permission_ids=permission_ids)
    )
    op.execute(
        sa
        .text('DELETE FROM permissions WHERE id IN :permission_ids')
        .bindparams(sa.bindparam('permission_ids', expanding=True))
        .bindparams(permission_ids=permission_ids)
    )
    op.drop_index(
        'ix_institutional_changes_created_at_id_desc',
        table_name='institutional_changes',
    )
    op.drop_table('institutional_changes')
    op.drop_index(
        'ix_affiliations_active_scope',
        table_name='user_institutional_affiliations',
    )
    op.drop_index(
        'uq_affiliations_active_laboratory',
        table_name='user_institutional_affiliations',
    )
    op.drop_index(
        'uq_affiliations_active_institution',
        table_name='user_institutional_affiliations',
    )
    op.drop_table('user_institutional_affiliations')
    op.drop_index(
        'ix_laboratories_institution_name_id', table_name='laboratories'
    )
    op.drop_index(
        'uq_laboratories_institution_name_ci_active', table_name='laboratories'
    )
    op.drop_table('laboratories')
    op.drop_index('ix_institutions_name_id', table_name='institutions')
    op.drop_index('uq_institutions_name_ci_active', table_name='institutions')
    op.drop_table('institutions')
