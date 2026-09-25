"""Process lifecycle and activity access grants (Spec 030, 1st revision).

- `process_instances.status` keeps only the lifecycle (OPEN, CLOSED,
  CANCELLED, ARCHIVED); flow positions become OPEN.
- `activity_instances.view_roles` / `edit_roles` store the per-cargo grants,
  backfilled from the canonical phase 1 matrix, the template definition or
  the latest task of the activity.

Revision ID: 3c9a1f2d7e40
Revises: 1b1772b71863
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '3c9a1f2d7e40'
down_revision: str | Sequence[str] | None = '1b1772b71863'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

FLOW_STATUSES = ('SUBMISSION', 'AI_PRE_EVALUATION', 'TRIAGE', 'PLANNING')
LIFECYCLE_CHECK = "status IN ('OPEN', 'CLOSED', 'CANCELLED', 'ARCHIVED')"
GLOBAL_VIEWERS = ('admin', 'bracvam')

# Matriz da fase 1 (data-model.md). Embutida aqui para a migração não
# depender dos YAMLs, que podem mudar depois.
PHASE1_EDIT_ROLES = {
    'proposal_submission': ['proponent'],
    'triage_evaluation': ['bracvam'],
}
# Cargos legados normalizados pela Spec 018.
LEGACY_ROLES = {
    'PROPONENT': 'proponent',
    'TRIAGE_LEAD': 'bracvam',
    'BRACVAM_ADMIN': 'bracvam',
}


def _normalize(role: str | None) -> str | None:
    if not role:
        return None
    return LEGACY_ROLES.get(role, role.lower())


def _payload_roles(payload: dict | None) -> dict[str, str]:
    roles = {}
    for phase in (payload or {}).get('phases', []):
        for activity in phase.get('activities', []):
            role = _normalize(activity.get('assigned_role'))
            if activity.get('key') and role:
                roles[activity['key']] = role
    return roles


def _backfill_activity_access(bind) -> None:
    activities = bind.execute(
        sa.text(
            'SELECT a.id, a.key, v.definition_payload, '
            '(SELECT t.assigned_role FROM activity_runs r '
            ' JOIN tasks t ON t.activity_run_id = r.id '
            ' WHERE r.activity_instance_id = a.id '
            ' ORDER BY r.run_number DESC, t.created_at DESC LIMIT 1) '
            'FROM activity_instances a '
            'JOIN process_instances p ON p.id = a.process_instance_id '
            'JOIN process_template_versions v ON v.id = p.template_version_id'
        )
    ).all()
    for activity_id, key, payload, task_role in activities:
        edit = PHASE1_EDIT_ROLES.get(key)
        if edit is None:
            role = (
                _payload_roles(payload).get(key)
                or _normalize(task_role)
                or 'proponent'
            )
            edit = [role]
        view = sorted(set(edit) | set(GLOBAL_VIEWERS))
        bind.execute(
            sa.text(
                'UPDATE activity_instances '
                'SET view_roles = :view, edit_roles = :edit WHERE id = :id'
            ),
            {'view': view, 'edit': sorted(edit), 'id': activity_id},
        )


def upgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "UPDATE process_instances SET status = 'OPEN' "
            'WHERE status IN :flow'
        ).bindparams(sa.bindparam('flow', expanding=True)),
        {'flow': list(FLOW_STATUSES)},
    )
    op.create_check_constraint(
        'ck_process_instances_status', 'process_instances', LIFECYCLE_CHECK
    )

    for column in ('view_roles', 'edit_roles'):
        op.add_column(
            'activity_instances',
            sa.Column(column, postgresql.ARRAY(sa.String(64)), nullable=True),
        )
    _backfill_activity_access(bind)
    for column in ('view_roles', 'edit_roles'):
        op.alter_column('activity_instances', column, nullable=False)


def downgrade() -> None:
    op.drop_column('activity_instances', 'edit_roles')
    op.drop_column('activity_instances', 'view_roles')
    op.drop_constraint(
        'ck_process_instances_status', 'process_instances', type_='check'
    )
    # Reconstrói a posição no fluxo a partir das atividades (FR-034), na
    # ordem de precedência do fluxo antigo.
    op.execute(
        """
        UPDATE process_instances p SET status = CASE
            WHEN EXISTS (
                SELECT 1 FROM evaluation_runs e
                WHERE e.process_instance_id = p.id
                  AND e.status = 'in_progress'
                  AND e.deleted_at IS NULL
            ) THEN 'AI_PRE_EVALUATION'
            WHEN EXISTS (
                SELECT 1 FROM activity_instances a
                WHERE a.process_instance_id = p.id
                  AND a.key = 'triage_evaluation'
                  AND a.status = 'IN_PROGRESS'
            ) THEN 'TRIAGE'
            WHEN EXISTS (
                SELECT 1 FROM phases f
                WHERE f.process_instance_id = p.id
                  AND f.order_index = 1
                  AND f.status = 'COMPLETED'
            ) THEN 'PLANNING'
            ELSE 'SUBMISSION'
        END
        WHERE p.status = 'OPEN'
        """
    )
