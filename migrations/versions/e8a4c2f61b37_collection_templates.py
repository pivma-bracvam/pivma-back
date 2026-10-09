"""Collection templates catalog (Spec 041, issue #26).

Creates the global catalog of data collection templates and their columns,
links a process to a template at creation time and inserts the
``collection_templates.manage`` permission. Existing processes keep the link
empty.

No profile composition is inserted: ``effective_permission_codes`` (Spec 023)
already grants every active permission to Administrator and BraCVAM, as in
``fa506675d3f9``.

Revision ID: e8a4c2f61b37
Revises: b7c3e1f2a9d4
"""

from collections.abc import Sequence
from uuid import UUID

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = 'e8a4c2f61b37'
down_revision: str | Sequence[str] | None = 'b7c3e1f2a9d4'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ACTIVE_ONLY = sa.text('deleted_at IS NULL')
COLLECTION_TEMPLATES_MANAGE_ID = UUID('00000000-0000-0000-0000-00000000010e')


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
        'collection_templates',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('min_experiments', sa.Integer(), nullable=False),
        sa.Column('min_replicates', sa.Integer(), nullable=False),
        *_audit_columns('collection_templates'),
        sa.CheckConstraint(
            'min_experiments >= 1',
            name='ck_collection_templates_min_experiments',
        ),
        sa.CheckConstraint(
            'min_replicates >= 1',
            name='ck_collection_templates_min_replicates',
        ),
    )

    op.create_table(
        'collection_template_columns',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column(
            'collection_template_id',
            sa.UUID(),
            sa.ForeignKey(
                'collection_templates.id',
                name='fk_collection_template_columns_collection_template_id',
            ),
            nullable=False,
        ),
        sa.Column('label', sa.String(255), nullable=False),
        sa.Column('key', sa.String(64), nullable=False),
        sa.Column('column_type', sa.String(16), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False),
        sa.Column('required', sa.Boolean(), nullable=False),
        sa.Column('options', JSONB(), nullable=True),
        *_audit_columns('collection_template_columns'),
        sa.CheckConstraint(
            "column_type IN ('text', 'integer', 'decimal', 'date', 'select')",
            name='ck_collection_template_columns_type',
        ),
        sa.CheckConstraint(
            'position >= 1', name='ck_collection_template_columns_position'
        ),
    )
    op.create_index(
        'uq_collection_template_columns_key_active',
        'collection_template_columns',
        ['collection_template_id', 'key'],
        unique=True,
        postgresql_where=ACTIVE_ONLY,
    )
    op.create_index(
        'uq_collection_template_columns_position_active',
        'collection_template_columns',
        ['collection_template_id', 'position'],
        unique=True,
        postgresql_where=ACTIVE_ONLY,
    )

    op.add_column(
        'process_instances',
        sa.Column(
            'collection_template_id',
            sa.UUID(),
            sa.ForeignKey(
                'collection_templates.id',
                name='fk_process_instances_collection_template_id',
            ),
            nullable=True,
        ),
    )
    op.create_index(
        'ix_process_instances_collection_template_id',
        'process_instances',
        ['collection_template_id'],
    )

    permissions = sa.table(
        'permissions',
        sa.column('id', sa.Uuid()),
        sa.column('code'),
        sa.column('description'),
    )
    op.bulk_insert(
        permissions,
        [
            dict(
                id=COLLECTION_TEMPLATES_MANAGE_ID,
                code='collection_templates.manage',
                description=(
                    'Gerir o catálogo de templates de coleta de dados '
                    '(colunas, mínimos e arquivo-modelo).'
                ),
            )
        ],
    )


def downgrade() -> None:
    # Bootstrap composes this permission onto the Administrator and BraCVAM
    # profiles. Remove active and soft-deleted mappings before the FK target.
    op.execute(
        'DELETE FROM access_profile_permissions '
        f"WHERE permission_id = '{COLLECTION_TEMPLATES_MANAGE_ID}'"
    )
    op.execute(
        'DELETE FROM permissions '
        f"WHERE id = '{COLLECTION_TEMPLATES_MANAGE_ID}'"
    )
    op.drop_index(
        'ix_process_instances_collection_template_id',
        table_name='process_instances',
    )
    op.drop_column('process_instances', 'collection_template_id')
    op.drop_index(
        'uq_collection_template_columns_position_active',
        table_name='collection_template_columns',
    )
    op.drop_index(
        'uq_collection_template_columns_key_active',
        table_name='collection_template_columns',
    )
    op.drop_table('collection_template_columns')
    op.drop_table('collection_templates')
