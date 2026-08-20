"""User authorization RBAC.

Revision ID: c1e4a9f8b312
Revises: 2d7f9a4c6b81
"""

from collections.abc import Sequence
from uuid import UUID

import sqlalchemy as sa
from alembic import op

revision: str = 'c1e4a9f8b312'
down_revision: str | Sequence[str] | None = '2d7f9a4c6b81'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ACTIVE_ONLY = sa.text('deleted_at IS NULL')
ADMIN_PROFILE_ID = UUID('00000000-0000-0000-0000-000000000009')
PERMISSIONS = (
    (
        UUID('00000000-0000-0000-0000-000000000101'),
        'rbac.read',
        'Consultar o estado do RBAC.',
    ),
    (
        UUID('00000000-0000-0000-0000-000000000102'),
        'rbac.profiles.manage',
        'Gerir perfis e suas permissões.',
    ),
    (
        UUID('00000000-0000-0000-0000-000000000103'),
        'rbac.assignments.manage',
        'Gerir atribuições de perfis.',
    ),
)
PROFILES = (
    (UUID('00000000-0000-0000-0000-000000000001'), 'proponent', 'Proponente'),
    (
        UUID('00000000-0000-0000-0000-000000000002'),
        'management_group',
        'Grupo Gestor',
    ),
    (
        UUID('00000000-0000-0000-0000-000000000003'),
        'study_manager',
        'Gerente do Estudo',
    ),
    (
        UUID('00000000-0000-0000-0000-000000000004'),
        'participating_laboratory',
        'Laboratório Participante',
    ),
    (
        UUID('00000000-0000-0000-0000-000000000005'),
        'ad_hoc_evaluator',
        'Avaliador Ad Hoc',
    ),
    (UUID('00000000-0000-0000-0000-000000000006'), 'reviewer', 'Revisor'),
    (
        UUID('00000000-0000-0000-0000-000000000007'),
        'specialist',
        'Especialista',
    ),
    (
        UUID('00000000-0000-0000-0000-000000000008'),
        'statistical_analyst',
        'Analista Estatístico',
    ),
    (ADMIN_PROFILE_ID, 'administrator', 'Administrador'),
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
        'access_profiles',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('system_key', sa.String(64), unique=True, nullable=True),
        sa.Column('name', sa.String(64), nullable=False),
        sa.Column('description', sa.String(500), nullable=False),
        *_audit_columns(),
    )
    op.create_index(
        'uq_access_profiles_name_ci_active',
        'access_profiles',
        [sa.text('lower(name)')],
        unique=True,
        postgresql_where=ACTIVE_ONLY,
    )
    op.create_table(
        'permissions',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('code', sa.String(100), unique=True, nullable=False),
        sa.Column('description', sa.String(500), nullable=False),
        *_audit_columns(),
    )
    op.create_table(
        'access_profile_permissions',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column(
            'profile_id',
            sa.UUID(),
            sa.ForeignKey('access_profiles.id'),
            nullable=False,
        ),
        sa.Column(
            'permission_id',
            sa.UUID(),
            sa.ForeignKey('permissions.id'),
            nullable=False,
        ),
        *_audit_columns(),
    )
    op.create_index(
        'uq_access_profile_permissions_active',
        'access_profile_permissions',
        ['profile_id', 'permission_id'],
        unique=True,
        postgresql_where=ACTIVE_ONLY,
    )
    op.create_table(
        'user_access_profiles',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column(
            'user_id', sa.UUID(), sa.ForeignKey('users.id'), nullable=False
        ),
        sa.Column(
            'profile_id',
            sa.UUID(),
            sa.ForeignKey('access_profiles.id'),
            nullable=False,
        ),
        *_audit_columns(),
    )
    op.create_index(
        'uq_user_access_profiles_active',
        'user_access_profiles',
        ['user_id', 'profile_id'],
        unique=True,
        postgresql_where=ACTIVE_ONLY,
    )
    op.create_table(
        'rbac_changes',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('action', sa.String(64), nullable=False),
        sa.Column('target_type', sa.String(32), nullable=False),
        sa.Column('target_id', sa.UUID(), nullable=False),
        *_audit_columns(),
    )
    op.create_index(
        'ix_rbac_changes_created_at_id_desc',
        'rbac_changes',
        [sa.text('created_at DESC'), sa.text('id DESC')],
    )

    profiles = sa.table(
        'access_profiles',
        sa.column('id', sa.UUID()),
        sa.column('system_key'),
        sa.column('name'),
        sa.column('description'),
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
        profiles,
        [
            dict(id=profile_id, system_key=key, name=name, description=name)
            for profile_id, key, name in PROFILES
        ],
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
            for i, (permission_id, _, _) in enumerate(PERMISSIONS, 1)
        ],
    )


def downgrade() -> None:
    op.drop_index(
        'ix_rbac_changes_created_at_id_desc', table_name='rbac_changes'
    )
    op.drop_table('rbac_changes')
    op.drop_index(
        'uq_user_access_profiles_active', table_name='user_access_profiles'
    )
    op.drop_table('user_access_profiles')
    op.drop_index(
        'uq_access_profile_permissions_active',
        table_name='access_profile_permissions',
    )
    op.drop_table('access_profile_permissions')
    op.drop_table('permissions')
    op.drop_index(
        'uq_access_profiles_name_ci_active', table_name='access_profiles'
    )
    op.drop_table('access_profiles')
