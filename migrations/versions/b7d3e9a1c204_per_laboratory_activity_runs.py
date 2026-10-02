"""Per-laboratory activity runs (Spec 036).

Adds the execution scope and custody flag to activity instances, the
laboratory to activity runs (run numbers now count per laboratory) and the
laboratory waivers table. Existing rows keep single execution behavior:
`execution_scope = 'process'`, `is_custody = false`, `laboratory_id` null.

Revision ID: b7d3e9a1c204
Revises: cc6c65843305
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'b7d3e9a1c204'
down_revision: str | Sequence[str] | None = 'cc6c65843305'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ACTIVE_ONLY = sa.text('deleted_at IS NULL')
RUN_INDEX = 'uq_activity_runs_number_active'


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
    op.add_column(
        'activity_instances',
        sa.Column(
            'execution_scope',
            sa.String(32),
            server_default='process',
            nullable=False,
        ),
    )
    op.add_column(
        'activity_instances',
        sa.Column(
            'is_custody',
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
    )
    op.add_column(
        'activity_runs',
        sa.Column(
            'laboratory_id',
            sa.UUID(),
            sa.ForeignKey(
                'laboratories.id', name='fk_activity_runs_laboratory_id'
            ),
            nullable=True,
        ),
    )
    op.drop_index(RUN_INDEX, table_name='activity_runs')
    op.create_index(
        RUN_INDEX,
        'activity_runs',
        ['activity_instance_id', 'laboratory_id', 'run_number'],
        unique=True,
        postgresql_nulls_not_distinct=True,
        postgresql_where=ACTIVE_ONLY,
    )

    op.create_table(
        'laboratory_waivers',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column(
            'process_instance_id',
            sa.UUID(),
            sa.ForeignKey(
                'process_instances.id',
                name='fk_laboratory_waivers_process_instance_id',
            ),
            nullable=False,
        ),
        sa.Column(
            'phase_id',
            sa.UUID(),
            sa.ForeignKey('phases.id', name='fk_laboratory_waivers_phase_id'),
            nullable=False,
        ),
        sa.Column(
            'laboratory_id',
            sa.UUID(),
            sa.ForeignKey(
                'laboratories.id', name='fk_laboratory_waivers_laboratory_id'
            ),
            nullable=False,
        ),
        sa.Column('reason', sa.Text(), nullable=False),
        *_audit_columns('laboratory_waivers'),
    )
    op.create_index(
        'uq_laboratory_waivers_phase_lab_active',
        'laboratory_waivers',
        ['phase_id', 'laboratory_id'],
        unique=True,
        postgresql_where=ACTIVE_ONLY,
    )


def downgrade() -> None:
    op.drop_index(
        'uq_laboratory_waivers_phase_lab_active',
        table_name='laboratory_waivers',
    )
    op.drop_table('laboratory_waivers')

    op.drop_index(RUN_INDEX, table_name='activity_runs')
    op.drop_column('activity_runs', 'laboratory_id')
    op.create_index(
        RUN_INDEX,
        'activity_runs',
        ['activity_instance_id', 'run_number'],
        unique=True,
        postgresql_where=ACTIVE_ONLY,
    )
    op.drop_column('activity_instances', 'is_custody')
    op.drop_column('activity_instances', 'execution_scope')
