"""process_submission_triage_core.

Revision ID: 1bd1b3d5ddad
Revises: c1e4a9f8b312
Create Date: 2026-08-21 09:18:46.000000

"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '1bd1b3d5ddad'
down_revision: Union[str, None] = 'c1e4a9f8b312'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ACTIVE_ONLY = sa.text('deleted_at IS NULL')


def upgrade() -> None:
    # 1. process_templates
    op.create_table(
        'process_templates',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('key', sa.String(length=64), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('created_by', sa.UUID(), nullable=True),
        sa.Column('updated_by', sa.UUID(), nullable=True),
        sa.Column('deleted_by', sa.UUID(), nullable=True),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], name='fk_process_templates_created_by', use_alter=True),
        sa.ForeignKeyConstraint(['updated_by'], ['users.id'], name='fk_process_templates_updated_by', use_alter=True),
        sa.ForeignKeyConstraint(['deleted_by'], ['users.id'], name='fk_process_templates_deleted_by', use_alter=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('key', name='uq_process_templates_key')
    )

    # 2. process_template_versions
    op.create_table(
        'process_template_versions',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('template_id', sa.UUID(), nullable=False),
        sa.Column('version_number', sa.Integer(), nullable=False),
        sa.Column('definition_payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('is_published', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('created_by', sa.UUID(), nullable=True),
        sa.Column('updated_by', sa.UUID(), nullable=True),
        sa.Column('deleted_by', sa.UUID(), nullable=True),
        sa.ForeignKeyConstraint(['template_id'], ['process_templates.id'], name='fk_process_template_versions_template_id'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], name='fk_process_template_versions_created_by', use_alter=True),
        sa.ForeignKeyConstraint(['updated_by'], ['users.id'], name='fk_process_template_versions_updated_by', use_alter=True),
        sa.ForeignKeyConstraint(['deleted_by'], ['users.id'], name='fk_process_template_versions_deleted_by', use_alter=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(
        'uq_process_template_version_active',
        'process_template_versions',
        ['template_id', 'version_number'],
        unique=True,
        postgresql_where=ACTIVE_ONLY
    )

    # 3. form_templates
    op.create_table(
        'form_templates',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('key', sa.String(length=64), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('version', sa.Integer(), server_default='1', nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('created_by', sa.UUID(), nullable=True),
        sa.Column('updated_by', sa.UUID(), nullable=True),
        sa.Column('deleted_by', sa.UUID(), nullable=True),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], name='fk_form_templates_created_by', use_alter=True),
        sa.ForeignKeyConstraint(['updated_by'], ['users.id'], name='fk_form_templates_updated_by', use_alter=True),
        sa.ForeignKeyConstraint(['deleted_by'], ['users.id'], name='fk_form_templates_deleted_by', use_alter=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('key', name='uq_form_templates_key')
    )

    # 4. form_fields
    op.create_table(
        'form_fields',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('form_template_id', sa.UUID(), nullable=False),
        sa.Column('field_key', sa.String(length=64), nullable=False),
        sa.Column('label', sa.String(length=255), nullable=False),
        sa.Column('help_text', sa.Text(), nullable=True),
        sa.Column('field_type', sa.String(length=32), nullable=False),
        sa.Column('is_required', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('order_index', sa.Integer(), server_default='0', nullable=False),
        sa.Column('options', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('validation_rules', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('created_by', sa.UUID(), nullable=True),
        sa.Column('updated_by', sa.UUID(), nullable=True),
        sa.Column('deleted_by', sa.UUID(), nullable=True),
        sa.ForeignKeyConstraint(['form_template_id'], ['form_templates.id'], name='fk_form_fields_form_template_id'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], name='fk_form_fields_created_by', use_alter=True),
        sa.ForeignKeyConstraint(['updated_by'], ['users.id'], name='fk_form_fields_updated_by', use_alter=True),
        sa.ForeignKeyConstraint(['deleted_by'], ['users.id'], name='fk_form_fields_deleted_by', use_alter=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(
        'uq_form_fields_key_active',
        'form_fields',
        ['form_template_id', 'field_key'],
        unique=True,
        postgresql_where=ACTIVE_ONLY
    )

    # 5. process_instances
    op.create_table(
        'process_instances',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('template_version_id', sa.UUID(), nullable=False),
        sa.Column('code', sa.String(length=32), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('status', sa.String(length=32), server_default='SUBMISSION', nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('closed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('closure_reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('created_by', sa.UUID(), nullable=True),
        sa.Column('updated_by', sa.UUID(), nullable=True),
        sa.Column('deleted_by', sa.UUID(), nullable=True),
        sa.ForeignKeyConstraint(['template_version_id'], ['process_template_versions.id'], name='fk_process_instances_template_version_id'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], name='fk_process_instances_created_by', use_alter=True),
        sa.ForeignKeyConstraint(['updated_by'], ['users.id'], name='fk_process_instances_updated_by', use_alter=True),
        sa.ForeignKeyConstraint(['deleted_by'], ['users.id'], name='fk_process_instances_deleted_by', use_alter=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code', name='uq_process_instances_code')
    )

    # 6. phases
    op.create_table(
        'phases',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('process_instance_id', sa.UUID(), nullable=False),
        sa.Column('key', sa.String(length=64), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('order_index', sa.Integer(), server_default='1', nullable=False),
        sa.Column('status', sa.String(length=32), server_default='NOT_STARTED', nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('created_by', sa.UUID(), nullable=True),
        sa.Column('updated_by', sa.UUID(), nullable=True),
        sa.Column('deleted_by', sa.UUID(), nullable=True),
        sa.ForeignKeyConstraint(['process_instance_id'], ['process_instances.id'], name='fk_phases_process_instance_id'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], name='fk_phases_created_by', use_alter=True),
        sa.ForeignKeyConstraint(['updated_by'], ['users.id'], name='fk_phases_updated_by', use_alter=True),
        sa.ForeignKeyConstraint(['deleted_by'], ['users.id'], name='fk_phases_deleted_by', use_alter=True),
        sa.PrimaryKeyConstraint('id')
    )

    # 7. activity_instances
    op.create_table(
        'activity_instances',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('process_instance_id', sa.UUID(), nullable=False),
        sa.Column('phase_id', sa.UUID(), nullable=False),
        sa.Column('key', sa.String(length=64), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('order_index', sa.Integer(), server_default='1', nullable=False),
        sa.Column('status', sa.String(length=32), server_default='BLOCKED', nullable=False),
        sa.Column('blocked_reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('created_by', sa.UUID(), nullable=True),
        sa.Column('updated_by', sa.UUID(), nullable=True),
        sa.Column('deleted_by', sa.UUID(), nullable=True),
        sa.ForeignKeyConstraint(['process_instance_id'], ['process_instances.id'], name='fk_activity_instances_process_instance_id'),
        sa.ForeignKeyConstraint(['phase_id'], ['phases.id'], name='fk_activity_instances_phase_id'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], name='fk_activity_instances_created_by', use_alter=True),
        sa.ForeignKeyConstraint(['updated_by'], ['users.id'], name='fk_activity_instances_updated_by', use_alter=True),
        sa.ForeignKeyConstraint(['deleted_by'], ['users.id'], name='fk_activity_instances_deleted_by', use_alter=True),
        sa.PrimaryKeyConstraint('id')
    )

    # 8. activity_runs
    op.create_table(
        'activity_runs',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('activity_instance_id', sa.UUID(), nullable=False),
        sa.Column('run_number', sa.Integer(), server_default='1', nullable=False),
        sa.Column('status', sa.String(length=32), server_default='IN_PROGRESS', nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('execution_reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('created_by', sa.UUID(), nullable=True),
        sa.Column('updated_by', sa.UUID(), nullable=True),
        sa.Column('deleted_by', sa.UUID(), nullable=True),
        sa.ForeignKeyConstraint(['activity_instance_id'], ['activity_instances.id'], name='fk_activity_runs_activity_instance_id'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], name='fk_activity_runs_created_by', use_alter=True),
        sa.ForeignKeyConstraint(['updated_by'], ['users.id'], name='fk_activity_runs_updated_by', use_alter=True),
        sa.ForeignKeyConstraint(['deleted_by'], ['users.id'], name='fk_activity_runs_deleted_by', use_alter=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(
        'uq_activity_runs_number_active',
        'activity_runs',
        ['activity_instance_id', 'run_number'],
        unique=True,
        postgresql_where=ACTIVE_ONLY
    )

    # 9. activity_dependencies
    op.create_table(
        'activity_dependencies',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('dependent_activity_id', sa.UUID(), nullable=False),
        sa.Column('required_activity_id', sa.UUID(), nullable=True),
        sa.Column('required_status', sa.String(length=32), server_default='COMPLETED', nullable=False),
        sa.Column('condition_type', sa.String(length=32), server_default='ACTIVITY_COMPLETED', nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('created_by', sa.UUID(), nullable=True),
        sa.Column('updated_by', sa.UUID(), nullable=True),
        sa.Column('deleted_by', sa.UUID(), nullable=True),
        sa.ForeignKeyConstraint(['dependent_activity_id'], ['activity_instances.id'], name='fk_activity_dependencies_dependent_activity_id'),
        sa.ForeignKeyConstraint(['required_activity_id'], ['activity_instances.id'], name='fk_activity_dependencies_required_activity_id'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], name='fk_activity_dependencies_created_by', use_alter=True),
        sa.ForeignKeyConstraint(['updated_by'], ['users.id'], name='fk_activity_dependencies_updated_by', use_alter=True),
        sa.ForeignKeyConstraint(['deleted_by'], ['users.id'], name='fk_activity_dependencies_deleted_by', use_alter=True),
        sa.PrimaryKeyConstraint('id')
    )

    # 10. tasks
    op.create_table(
        'tasks',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('activity_run_id', sa.UUID(), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('assigned_role', sa.String(length=64), nullable=True),
        sa.Column('assigned_user_id', sa.UUID(), nullable=True),
        sa.Column('status', sa.String(length=32), server_default='READY', nullable=False),
        sa.Column('due_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('created_by', sa.UUID(), nullable=True),
        sa.Column('updated_by', sa.UUID(), nullable=True),
        sa.Column('deleted_by', sa.UUID(), nullable=True),
        sa.ForeignKeyConstraint(['activity_run_id'], ['activity_runs.id'], name='fk_tasks_activity_run_id'),
        sa.ForeignKeyConstraint(['assigned_user_id'], ['users.id'], name='fk_tasks_assigned_user_id'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], name='fk_tasks_created_by', use_alter=True),
        sa.ForeignKeyConstraint(['updated_by'], ['users.id'], name='fk_tasks_updated_by', use_alter=True),
        sa.ForeignKeyConstraint(['deleted_by'], ['users.id'], name='fk_tasks_deleted_by', use_alter=True),
        sa.PrimaryKeyConstraint('id')
    )

    # 11. artifacts
    op.create_table(
        'artifacts',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('process_instance_id', sa.UUID(), nullable=False),
        sa.Column('activity_run_id', sa.UUID(), nullable=False),
        sa.Column('key', sa.String(length=64), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('file_path', sa.String(length=500), nullable=True),
        sa.Column('file_size', sa.BigInteger(), nullable=True),
        sa.Column('mime_type', sa.String(length=128), nullable=True),
        sa.Column('checksum_sha256', sa.String(length=64), nullable=True),
        sa.Column('metadata_payload', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('status', sa.String(length=32), server_default='SUBMITTED', nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('created_by', sa.UUID(), nullable=True),
        sa.Column('updated_by', sa.UUID(), nullable=True),
        sa.Column('deleted_by', sa.UUID(), nullable=True),
        sa.ForeignKeyConstraint(['process_instance_id'], ['process_instances.id'], name='fk_artifacts_process_instance_id'),
        sa.ForeignKeyConstraint(['activity_run_id'], ['activity_runs.id'], name='fk_artifacts_activity_run_id'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], name='fk_artifacts_created_by', use_alter=True),
        sa.ForeignKeyConstraint(['updated_by'], ['users.id'], name='fk_artifacts_updated_by', use_alter=True),
        sa.ForeignKeyConstraint(['deleted_by'], ['users.id'], name='fk_artifacts_deleted_by', use_alter=True),
        sa.PrimaryKeyConstraint('id')
    )

    # 12. form_instances
    op.create_table(
        'form_instances',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('form_template_id', sa.UUID(), nullable=False),
        sa.Column('activity_run_id', sa.UUID(), nullable=False),
        sa.Column('is_submitted', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('submitted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('created_by', sa.UUID(), nullable=True),
        sa.Column('updated_by', sa.UUID(), nullable=True),
        sa.Column('deleted_by', sa.UUID(), nullable=True),
        sa.ForeignKeyConstraint(['form_template_id'], ['form_templates.id'], name='fk_form_instances_form_template_id'),
        sa.ForeignKeyConstraint(['activity_run_id'], ['activity_runs.id'], name='fk_form_instances_activity_run_id'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], name='fk_form_instances_created_by', use_alter=True),
        sa.ForeignKeyConstraint(['updated_by'], ['users.id'], name='fk_form_instances_updated_by', use_alter=True),
        sa.ForeignKeyConstraint(['deleted_by'], ['users.id'], name='fk_form_instances_deleted_by', use_alter=True),
        sa.PrimaryKeyConstraint('id')
    )

    # 13. form_values
    op.create_table(
        'form_values',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('form_instance_id', sa.UUID(), nullable=False),
        sa.Column('form_field_id', sa.UUID(), nullable=False),
        sa.Column('text_value', sa.Text(), nullable=True),
        sa.Column('numeric_value', sa.Numeric(), nullable=True),
        sa.Column('boolean_value', sa.Boolean(), nullable=True),
        sa.Column('date_value', sa.Date(), nullable=True),
        sa.Column('json_value', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('file_attachment_id', sa.UUID(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('created_by', sa.UUID(), nullable=True),
        sa.Column('updated_by', sa.UUID(), nullable=True),
        sa.Column('deleted_by', sa.UUID(), nullable=True),
        sa.ForeignKeyConstraint(['form_instance_id'], ['form_instances.id'], name='fk_form_values_form_instance_id'),
        sa.ForeignKeyConstraint(['form_field_id'], ['form_fields.id'], name='fk_form_values_form_field_id'),
        sa.ForeignKeyConstraint(['file_attachment_id'], ['artifacts.id'], name='fk_form_values_file_attachment_id'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], name='fk_form_values_created_by', use_alter=True),
        sa.ForeignKeyConstraint(['updated_by'], ['users.id'], name='fk_form_values_updated_by', use_alter=True),
        sa.ForeignKeyConstraint(['deleted_by'], ['users.id'], name='fk_form_values_deleted_by', use_alter=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(
        'uq_form_values_active',
        'form_values',
        ['form_instance_id', 'form_field_id'],
        unique=True,
        postgresql_where=ACTIVE_ONLY
    )

    # 14. field_reviews
    op.create_table(
        'field_reviews',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('form_instance_id', sa.UUID(), nullable=False),
        sa.Column('form_field_id', sa.UUID(), nullable=False),
        sa.Column('activity_run_id', sa.UUID(), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('comments', sa.Text(), nullable=True),
        sa.Column('reviewed_by', sa.UUID(), nullable=False),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('created_by', sa.UUID(), nullable=True),
        sa.Column('updated_by', sa.UUID(), nullable=True),
        sa.Column('deleted_by', sa.UUID(), nullable=True),
        sa.ForeignKeyConstraint(['form_instance_id'], ['form_instances.id'], name='fk_field_reviews_form_instance_id'),
        sa.ForeignKeyConstraint(['form_field_id'], ['form_fields.id'], name='fk_field_reviews_form_field_id'),
        sa.ForeignKeyConstraint(['activity_run_id'], ['activity_runs.id'], name='fk_field_reviews_activity_run_id'),
        sa.ForeignKeyConstraint(['reviewed_by'], ['users.id'], name='fk_field_reviews_reviewed_by'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], name='fk_field_reviews_created_by', use_alter=True),
        sa.ForeignKeyConstraint(['updated_by'], ['users.id'], name='fk_field_reviews_updated_by', use_alter=True),
        sa.ForeignKeyConstraint(['deleted_by'], ['users.id'], name='fk_field_reviews_deleted_by', use_alter=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(
        'uq_field_reviews_active',
        'field_reviews',
        ['form_instance_id', 'form_field_id', 'activity_run_id'],
        unique=True,
        postgresql_where=ACTIVE_ONLY
    )

    # 15. decisions
    op.create_table(
        'decisions',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('process_instance_id', sa.UUID(), nullable=False),
        sa.Column('activity_run_id', sa.UUID(), nullable=False),
        sa.Column('decision_type', sa.String(length=64), nullable=False),
        sa.Column('outcome', sa.String(length=32), nullable=False),
        sa.Column('justification', sa.Text(), nullable=False),
        sa.Column('decided_by', sa.UUID(), nullable=False),
        sa.Column('decided_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('created_by', sa.UUID(), nullable=True),
        sa.Column('updated_by', sa.UUID(), nullable=True),
        sa.Column('deleted_by', sa.UUID(), nullable=True),
        sa.ForeignKeyConstraint(['process_instance_id'], ['process_instances.id'], name='fk_decisions_process_instance_id'),
        sa.ForeignKeyConstraint(['activity_run_id'], ['activity_runs.id'], name='fk_decisions_activity_run_id'),
        sa.ForeignKeyConstraint(['decided_by'], ['users.id'], name='fk_decisions_decided_by'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], name='fk_decisions_created_by', use_alter=True),
        sa.ForeignKeyConstraint(['updated_by'], ['users.id'], name='fk_decisions_updated_by', use_alter=True),
        sa.ForeignKeyConstraint(['deleted_by'], ['users.id'], name='fk_decisions_deleted_by', use_alter=True),
        sa.PrimaryKeyConstraint('id')
    )

    # 16. assignments
    op.create_table(
        'assignments',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('process_instance_id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('role_key', sa.String(length=64), nullable=False),
        sa.Column('assigned_by', sa.UUID(), nullable=False),
        sa.Column('assigned_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('created_by', sa.UUID(), nullable=True),
        sa.Column('updated_by', sa.UUID(), nullable=True),
        sa.Column('deleted_by', sa.UUID(), nullable=True),
        sa.ForeignKeyConstraint(['process_instance_id'], ['process_instances.id'], name='fk_assignments_process_instance_id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name='fk_assignments_user_id'),
        sa.ForeignKeyConstraint(['assigned_by'], ['users.id'], name='fk_assignments_assigned_by'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], name='fk_assignments_created_by', use_alter=True),
        sa.ForeignKeyConstraint(['updated_by'], ['users.id'], name='fk_assignments_updated_by', use_alter=True),
        sa.ForeignKeyConstraint(['deleted_by'], ['users.id'], name='fk_assignments_deleted_by', use_alter=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(
        'uq_assignments_active',
        'assignments',
        ['process_instance_id', 'user_id', 'role_key'],
        unique=True,
        postgresql_where=sa.text('revoked_at IS NULL AND deleted_at IS NULL')
    )

    # 17. audit_events
    op.create_table(
        'audit_events',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('process_instance_id', sa.UUID(), nullable=False),
        sa.Column('activity_run_id', sa.UUID(), nullable=True),
        sa.Column('user_id', sa.UUID(), nullable=True),
        sa.Column('event_type', sa.String(length=64), nullable=False),
        sa.Column('context_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('occurred_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('created_by', sa.UUID(), nullable=True),
        sa.Column('updated_by', sa.UUID(), nullable=True),
        sa.Column('deleted_by', sa.UUID(), nullable=True),
        sa.ForeignKeyConstraint(['process_instance_id'], ['process_instances.id'], name='fk_audit_events_process_instance_id'),
        sa.ForeignKeyConstraint(['activity_run_id'], ['activity_runs.id'], name='fk_audit_events_activity_run_id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name='fk_audit_events_user_id'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], name='fk_audit_events_created_by', use_alter=True),
        sa.ForeignKeyConstraint(['updated_by'], ['users.id'], name='fk_audit_events_updated_by', use_alter=True),
        sa.ForeignKeyConstraint(['deleted_by'], ['users.id'], name='fk_audit_events_deleted_by', use_alter=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(
        'ix_audit_events_process_time',
        'audit_events',
        ['process_instance_id', sa.text('occurred_at DESC')],
        unique=False
    )


def downgrade() -> None:
    op.drop_table('audit_events')
    op.drop_table('assignments')
    op.drop_table('decisions')
    op.drop_table('field_reviews')
    op.drop_table('form_values')
    op.drop_table('form_instances')
    op.drop_table('artifacts')
    op.drop_table('tasks')
    op.drop_table('activity_dependencies')
    op.drop_table('activity_runs')
    op.drop_table('activity_instances')
    op.drop_table('phases')
    op.drop_table('process_instances')
    op.drop_table('form_fields')
    op.drop_table('form_templates')
    op.drop_table('process_template_versions')
    op.drop_table('process_templates')
