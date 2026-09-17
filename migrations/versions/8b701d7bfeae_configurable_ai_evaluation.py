"""configurable_ai_evaluation

Revision ID: 8b701d7bfeae
Revises: 62eee61a6ad3
Create Date: 2026-09-10

Spec 013 — Avaliação Configurável por IA na Submissão e Triagem.
Cria as tabelas de configuração/execução da avaliação por IA e semeia
as permissões RBAC ``ai_evaluations.read`` / ``ai_evaluations.manage``,
concedidas apenas ao perfil Administrador (demais perfis recebem via API,
como todo o restante do catálogo).
"""

from collections.abc import Sequence
from uuid import UUID

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '8b701d7bfeae'
down_revision: str | Sequence[str] | None = '62eee61a6ad3'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

READ_PERMISSION_ID = UUID('00000000-0000-0000-0000-00000000010a')
MANAGE_PERMISSION_ID = UUID('00000000-0000-0000-0000-00000000010b')
ADMIN_PROFILE_ID = UUID('00000000-0000-0000-0000-000000000009')
COMPOSITION_ADMIN_READ_ID = UUID('00000000-0000-0000-0000-00000000020a')
COMPOSITION_ADMIN_MANAGE_ID = UUID('00000000-0000-0000-0000-00000000020b')


def _audit_columns() -> list[sa.Column]:
    return [
        sa.Column(
            'created_at',
            sa.DateTime(),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('created_by', sa.Uuid(), nullable=True),
        sa.Column('updated_by', sa.Uuid(), nullable=True),
        sa.Column('deleted_by', sa.Uuid(), nullable=True),
    ]


def _audit_fks(table: str) -> list[sa.ForeignKeyConstraint]:
    return [
        sa.ForeignKeyConstraint(
            [col], ['users.id'], name=f'fk_{table}_{col}', use_alter=True
        )
        for col in ('created_by', 'updated_by', 'deleted_by')
    ]


def upgrade() -> None:
    op.create_table(
        'evaluation_definitions',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('slug', sa.String(length=80), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('mode', sa.String(length=16), nullable=False),
        *_audit_columns(),
        *_audit_fks('evaluation_definitions'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'uq_evaluation_definitions_slug_active',
        'evaluation_definitions',
        ['slug'],
        unique=True,
        postgresql_where=sa.text('deleted_at IS NULL'),
    )

    op.create_table(
        'evaluation_references',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('identifier', sa.String(length=64), nullable=False),
        sa.Column('label', sa.String(length=255), nullable=False),
        sa.Column('version_label', sa.String(length=64), nullable=False),
        sa.Column('reference_date', sa.Date(), nullable=True),
        *_audit_columns(),
        *_audit_fks('evaluation_references'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'uq_evaluation_references_id_version_active',
        'evaluation_references',
        ['identifier', 'version_label'],
        unique=True,
        postgresql_where=sa.text('deleted_at IS NULL'),
    )

    op.create_table(
        'evaluation_versions',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('definition_id', sa.Uuid(), nullable=False),
        sa.Column('version_number', sa.Integer(), nullable=False),
        sa.Column('objective', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=16), nullable=False),
        sa.Column(
            'references',
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column('test_run_count', sa.Integer(), nullable=False),
        sa.Column('published_at', sa.DateTime(), nullable=True),
        sa.Column('published_by', sa.Uuid(), nullable=True),
        *_audit_columns(),
        sa.ForeignKeyConstraint(
            ['definition_id'], ['evaluation_definitions.id']
        ),
        sa.ForeignKeyConstraint(['published_by'], ['users.id']),
        *_audit_fks('evaluation_versions'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'uq_evaluation_versions_number_active',
        'evaluation_versions',
        ['definition_id', 'version_number'],
        unique=True,
        postgresql_where=sa.text('deleted_at IS NULL'),
    )
    op.create_index(
        'uq_evaluation_versions_single_draft',
        'evaluation_versions',
        ['definition_id'],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL AND status = 'draft'"),
    )

    op.create_table(
        'evaluation_criteria',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('version_id', sa.Uuid(), nullable=False),
        sa.Column('statement', sa.Text(), nullable=False),
        sa.Column('check_type', sa.String(length=32), nullable=False),
        sa.Column('order_index', sa.Integer(), nullable=False),
        sa.Column('polarity', sa.String(length=16), nullable=False),
        sa.Column('required_evidence', sa.Text(), nullable=True),
        sa.Column('severity', sa.String(length=16), nullable=False),
        sa.Column('on_missing_info', sa.String(length=16), nullable=False),
        sa.Column('recommendation_hint', sa.Text(), nullable=True),
        *_audit_columns(),
        sa.ForeignKeyConstraint(
            ['version_id'], ['evaluation_versions.id']
        ),
        *_audit_fks('evaluation_criteria'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'ix_evaluation_criteria_version_order',
        'evaluation_criteria',
        ['version_id', 'order_index'],
        unique=False,
    )

    op.create_table(
        'evaluation_assignments',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('form_template_id', sa.Uuid(), nullable=False),
        sa.Column('definition_id', sa.Uuid(), nullable=False),
        sa.Column('target_type', sa.String(length=16), nullable=False),
        sa.Column('pinned_version_id', sa.Uuid(), nullable=True),
        sa.Column(
            'field_keys',
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column('enabled', sa.Boolean(), nullable=False),
        *_audit_columns(),
        sa.ForeignKeyConstraint(
            ['definition_id'], ['evaluation_definitions.id']
        ),
        sa.ForeignKeyConstraint(
            ['form_template_id'], ['form_templates.id']
        ),
        sa.ForeignKeyConstraint(
            ['pinned_version_id'], ['evaluation_versions.id']
        ),
        *_audit_fks('evaluation_assignments'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'ix_evaluation_assignments_template',
        'evaluation_assignments',
        ['form_template_id'],
        unique=False,
    )
    op.create_index(
        'uq_evaluation_assignments_active',
        'evaluation_assignments',
        ['form_template_id', 'definition_id', 'target_type'],
        unique=True,
        postgresql_where=sa.text('deleted_at IS NULL'),
    )

    op.create_table(
        'evaluation_runs',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('process_instance_id', sa.Uuid(), nullable=False),
        sa.Column('activity_run_id', sa.Uuid(), nullable=False),
        sa.Column('form_instance_id', sa.Uuid(), nullable=False),
        sa.Column('correlation_id', sa.Uuid(), nullable=False),
        sa.Column('status', sa.String(length=16), nullable=False),
        sa.Column('consolidated_result', sa.String(length=16), nullable=True),
        sa.Column('provider_name', sa.String(length=32), nullable=True),
        sa.Column(
            'models_used',
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column('real_cost', sa.Float(), nullable=False),
        sa.Column(
            'started_at',
            sa.DateTime(),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.Column('finished_at', sa.DateTime(), nullable=True),
        sa.Column('error_summary', sa.Text(), nullable=True),
        *_audit_columns(),
        sa.ForeignKeyConstraint(
            ['activity_run_id'], ['activity_runs.id']
        ),
        sa.ForeignKeyConstraint(
            ['form_instance_id'], ['form_instances.id']
        ),
        sa.ForeignKeyConstraint(
            ['process_instance_id'], ['process_instances.id']
        ),
        *_audit_fks('evaluation_runs'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'ix_evaluation_runs_process_time',
        'evaluation_runs',
        ['process_instance_id', sa.literal_column('started_at DESC')],
        unique=False,
    )
    op.create_index(
        'ix_evaluation_runs_status',
        'evaluation_runs',
        ['status'],
        unique=False,
    )

    op.create_table(
        'evaluation_run_items',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('run_id', sa.Uuid(), nullable=False),
        sa.Column('criterion_statement', sa.Text(), nullable=False),
        sa.Column('check_type', sa.String(length=32), nullable=False),
        sa.Column('polarity', sa.String(length=16), nullable=False),
        sa.Column('severity', sa.String(length=16), nullable=False),
        sa.Column('conclusion', sa.String(length=16), nullable=False),
        sa.Column('is_alert', sa.Boolean(), nullable=False),
        sa.Column('criterion_id', sa.Uuid(), nullable=True),
        sa.Column('evaluation_version_id', sa.Uuid(), nullable=True),
        sa.Column('evidence_excerpt', sa.Text(), nullable=True),
        sa.Column('evidence_location', sa.Text(), nullable=True),
        sa.Column('justification', sa.Text(), nullable=True),
        sa.Column('recommendation', sa.Text(), nullable=True),
        sa.Column('inference_confidence', sa.Float(), nullable=True),
        sa.Column(
            'evidence_completeness', sa.String(length=16), nullable=True
        ),
        sa.Column('model_layer', sa.String(length=16), nullable=False),
        *_audit_columns(),
        sa.ForeignKeyConstraint(
            ['criterion_id'], ['evaluation_criteria.id']
        ),
        sa.ForeignKeyConstraint(
            ['evaluation_version_id'], ['evaluation_versions.id']
        ),
        sa.ForeignKeyConstraint(['run_id'], ['evaluation_runs.id']),
        *_audit_fks('evaluation_run_items'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'ix_evaluation_run_items_criterion',
        'evaluation_run_items',
        ['criterion_id'],
        unique=False,
    )
    op.create_index(
        'ix_evaluation_run_items_run',
        'evaluation_run_items',
        ['run_id'],
        unique=False,
    )

    op.create_table(
        'direct_review_requests',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('evaluation_run_id', sa.Uuid(), nullable=False),
        sa.Column('process_instance_id', sa.Uuid(), nullable=False),
        sa.Column('requested_by', sa.Uuid(), nullable=False),
        sa.Column('justification', sa.Text(), nullable=True),
        *_audit_columns(),
        sa.ForeignKeyConstraint(
            ['evaluation_run_id'], ['evaluation_runs.id']
        ),
        sa.ForeignKeyConstraint(
            ['process_instance_id'], ['process_instances.id']
        ),
        sa.ForeignKeyConstraint(['requested_by'], ['users.id']),
        *_audit_fks('direct_review_requests'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'uq_direct_review_requests_run_active',
        'direct_review_requests',
        ['evaluation_run_id'],
        unique=True,
        postgresql_where=sa.text('deleted_at IS NULL'),
    )

    op.create_table(
        'reviewer_feedback',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('run_item_id', sa.Uuid(), nullable=False),
        sa.Column('reviewer_id', sa.Uuid(), nullable=False),
        sa.Column('verdict', sa.String(length=16), nullable=False),
        sa.Column('reason', sa.Text(), nullable=True),
        *_audit_columns(),
        sa.ForeignKeyConstraint(['reviewer_id'], ['users.id']),
        sa.ForeignKeyConstraint(
            ['run_item_id'], ['evaluation_run_items.id']
        ),
        *_audit_fks('reviewer_feedback'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'uq_reviewer_feedback_item_reviewer_active',
        'reviewer_feedback',
        ['run_item_id', 'reviewer_id'],
        unique=True,
        postgresql_where=sa.text('deleted_at IS NULL'),
    )

    op.create_table(
        'evaluation_test_runs',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('version_id', sa.Uuid(), nullable=False),
        sa.Column('sample_content', sa.Text(), nullable=False),
        sa.Column(
            'result_payload',
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column('real_cost', sa.Float(), nullable=False),
        *_audit_columns(),
        sa.ForeignKeyConstraint(
            ['version_id'], ['evaluation_versions.id']
        ),
        *_audit_fks('evaluation_test_runs'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'ix_evaluation_test_runs_version_time',
        'evaluation_test_runs',
        ['version_id', sa.literal_column('created_at DESC')],
        unique=False,
    )


def downgrade() -> None:
    for table in (
        'evaluation_test_runs',
        'reviewer_feedback',
        'direct_review_requests',
        'evaluation_run_items',
        'evaluation_runs',
        'evaluation_assignments',
        'evaluation_criteria',
        'evaluation_versions',
        'evaluation_references',
        'evaluation_definitions',
    ):
        op.drop_table(table)
