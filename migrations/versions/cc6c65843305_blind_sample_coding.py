"""Blind sample coding (Spec 031).

Creates the study substances registered by the sample selection group and
the blind codes, one per substance and participating laboratory. Existing
processes are untouched: they keep their template versions.

Revision ID: cc6c65843305
Revises: 7e21b4c0a9d3
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'cc6c65843305'
down_revision: str | Sequence[str] | None = '7e21b4c0a9d3'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ACTIVE_ONLY = sa.text('deleted_at IS NULL')


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
        'study_substances',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column(
            'process_instance_id',
            sa.UUID(),
            sa.ForeignKey(
                'process_instances.id',
                name='fk_study_substances_process_instance_id',
            ),
            nullable=False,
        ),
        sa.Column('chemical_name', sa.String(255), nullable=False),
        sa.Column('cas_number', sa.String(12), nullable=False),
        sa.Column('lot', sa.String(64), nullable=False),
        sa.Column('safe_handling_instructions', sa.Text(), nullable=False),
        sa.Column('purity', sa.String(64), nullable=True),
        sa.Column('solubility', sa.Text(), nullable=True),
        sa.Column(
            'sds_artifact_id',
            sa.UUID(),
            sa.ForeignKey(
                'artifacts.id', name='fk_study_substances_sds_artifact_id'
            ),
            nullable=True,
        ),
        *_audit_columns('study_substances'),
    )
    op.create_index(
        'uq_study_substances_process_cas_active',
        'study_substances',
        ['process_instance_id', 'cas_number'],
        unique=True,
        postgresql_where=ACTIVE_ONLY,
    )

    op.create_table(
        'blind_sample_codes',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column(
            'process_instance_id',
            sa.UUID(),
            sa.ForeignKey(
                'process_instances.id',
                name='fk_blind_sample_codes_process_instance_id',
            ),
            nullable=False,
        ),
        sa.Column(
            'substance_id',
            sa.UUID(),
            sa.ForeignKey(
                'study_substances.id',
                name='fk_blind_sample_codes_substance_id',
            ),
            nullable=False,
        ),
        sa.Column(
            'laboratory_id',
            sa.UUID(),
            sa.ForeignKey(
                'laboratories.id', name='fk_blind_sample_codes_laboratory_id'
            ),
            nullable=False,
        ),
        sa.Column('code', sa.String(8), nullable=False),
        *_audit_columns('blind_sample_codes'),
    )
    op.create_index(
        'uq_blind_sample_codes_process_code_active',
        'blind_sample_codes',
        ['process_instance_id', 'code'],
        unique=True,
        postgresql_where=ACTIVE_ONLY,
    )
    op.create_index(
        'uq_blind_sample_codes_substance_lab_active',
        'blind_sample_codes',
        ['substance_id', 'laboratory_id'],
        unique=True,
        postgresql_where=ACTIVE_ONLY,
    )


def downgrade() -> None:
    op.drop_index(
        'uq_blind_sample_codes_substance_lab_active',
        table_name='blind_sample_codes',
    )
    op.drop_index(
        'uq_blind_sample_codes_process_code_active',
        table_name='blind_sample_codes',
    )
    op.drop_table('blind_sample_codes')
    op.drop_index(
        'uq_study_substances_process_cas_active',
        table_name='study_substances',
    )
    op.drop_table('study_substances')
