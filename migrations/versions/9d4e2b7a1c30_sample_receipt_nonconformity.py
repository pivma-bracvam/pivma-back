"""Sample receipt, nonconformities and expanded substances (Spec 040).

Adds the reference classification, storage temperature, vial, reserve and
GHS columns to study_substances; the replaced-code link to
blind_sample_codes; and the sample_receipts and
sample_receipt_nonconformities tables. Existing substances keep the new
columns empty and a reserve of zero.

Revision ID: 9d4e2b7a1c30
Revises: 6fe19f1c95e9
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '9d4e2b7a1c30'
down_revision: str | Sequence[str] | None = '6fe19f1c95e9'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ACTIVE_ONLY = sa.text('deleted_at IS NULL')
RECEIPTS = 'sample_receipts'
NONCONFORMITIES = 'sample_receipt_nonconformities'


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


def _fk(table: str, column: str, target: str) -> sa.Column:
    return sa.Column(
        column,
        sa.UUID(),
        sa.ForeignKey(target, name=f'fk_{table}_{column}'),
        nullable=False,
    )


def upgrade() -> None:
    substances = [
        sa.Column('reference_classification', sa.Text(), nullable=True),
        sa.Column(
            'storage_temperature_regime', sa.String(16), nullable=True
        ),
        sa.Column('storage_temperature_min', sa.Float(), nullable=True),
        sa.Column('storage_temperature_max', sa.Float(), nullable=True),
        sa.Column('vial_nominal_quantity', sa.Float(), nullable=True),
        sa.Column('vial_unit', sa.String(16), nullable=True),
        sa.Column('packaging_type', sa.String(255), nullable=True),
        sa.Column('expiration_date', sa.Date(), nullable=True),
        sa.Column(
            'reserve_vials_count',
            sa.Integer(),
            server_default='0',
            nullable=False,
        ),
        sa.Column(
            'ghs_hazard_pictograms',
            postgresql.ARRAY(sa.String(5)),
            server_default='{}',
            nullable=False,
        ),
    ]
    for column in substances:
        op.add_column('study_substances', column)

    op.add_column(
        'blind_sample_codes',
        sa.Column(
            'replaces_code_id',
            sa.UUID(),
            sa.ForeignKey(
                'blind_sample_codes.id',
                name='fk_blind_sample_codes_replaces_code_id',
            ),
            nullable=True,
        ),
    )

    op.create_table(
        RECEIPTS,
        sa.Column('id', sa.UUID(), primary_key=True),
        _fk(RECEIPTS, 'process_instance_id', 'process_instances.id'),
        _fk(RECEIPTS, 'activity_run_id', 'activity_runs.id'),
        _fk(RECEIPTS, 'blind_sample_code_id', 'blind_sample_codes.id'),
        _fk(RECEIPTS, 'laboratory_id', 'laboratories.id'),
        sa.Column('opened_at', sa.DateTime(), nullable=False),
        sa.Column('temperature_celsius', sa.Float(), nullable=False),
        sa.Column('package_state', sa.String(16), nullable=False),
        sa.Column('conforming', sa.Boolean(), nullable=False),
        sa.Column(
            'deviations', postgresql.ARRAY(sa.String(32)), nullable=False
        ),
        sa.Column('notes', sa.Text(), nullable=True),
        *_audit_columns(RECEIPTS),
    )
    op.create_index(
        'uq_sample_receipts_code_active',
        RECEIPTS,
        ['blind_sample_code_id'],
        unique=True,
        postgresql_where=ACTIVE_ONLY,
    )

    op.create_table(
        NONCONFORMITIES,
        sa.Column('id', sa.UUID(), primary_key=True),
        _fk(NONCONFORMITIES, 'process_instance_id', 'process_instances.id'),
        _fk(NONCONFORMITIES, 'receipt_id', 'sample_receipts.id'),
        _fk(NONCONFORMITIES, 'laboratory_id', 'laboratories.id'),
        sa.Column('status', sa.String(16), nullable=False),
        sa.Column('decision', sa.String(32), nullable=True),
        sa.Column('justification', sa.Text(), nullable=True),
        sa.Column(
            'decided_by',
            sa.UUID(),
            sa.ForeignKey(
                'users.id', name=f'fk_{NONCONFORMITIES}_decided_by'
            ),
            nullable=True,
        ),
        sa.Column('decided_at', sa.DateTime(), nullable=True),
        sa.Column(
            'replacement_code_id',
            sa.UUID(),
            sa.ForeignKey(
                'blind_sample_codes.id',
                name=f'fk_{NONCONFORMITIES}_replacement_code_id',
            ),
            nullable=True,
        ),
        *_audit_columns(NONCONFORMITIES),
        sa.UniqueConstraint(
            'receipt_id', name=f'uq_{NONCONFORMITIES}_receipt_id'
        ),
    )
    op.create_index(
        'ix_sample_receipt_nonconformities_process_status',
        NONCONFORMITIES,
        ['process_instance_id', 'status'],
    )


def downgrade() -> None:
    op.drop_index(
        'ix_sample_receipt_nonconformities_process_status',
        table_name=NONCONFORMITIES,
    )
    op.drop_table(NONCONFORMITIES)
    op.drop_index('uq_sample_receipts_code_active', table_name=RECEIPTS)
    op.drop_table(RECEIPTS)
    op.drop_column('blind_sample_codes', 'replaces_code_id')
    for column in (
        'ghs_hazard_pictograms',
        'reserve_vials_count',
        'expiration_date',
        'packaging_type',
        'vial_unit',
        'vial_nominal_quantity',
        'storage_temperature_max',
        'storage_temperature_min',
        'storage_temperature_regime',
        'reference_classification',
    ):
        op.drop_column('study_substances', column)
