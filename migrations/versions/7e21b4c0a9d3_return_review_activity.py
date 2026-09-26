"""Return review activity for existing processes (Spec 030, 2nd revision).

Every process gains a blocked `submission_return_review` activity in its
first phase. Processes whose submission was already reopened by an older
return keep that open submission; no return review is opened retroactively.

Revision ID: 7e21b4c0a9d3
Revises: 3c9a1f2d7e40
"""

from collections.abc import Sequence

from alembic import op

revision: str = '7e21b4c0a9d3'
down_revision: str | Sequence[str] | None = '3c9a1f2d7e40'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

RETURN_REVIEW_RUNS = """
    SELECT r.id FROM activity_runs r
    JOIN activity_instances a ON a.id = r.activity_instance_id
    WHERE a.key = 'submission_return_review'
"""


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO activity_instances (
            id, process_instance_id, phase_id, key, name, order_index,
            status, blocked_reason, activity_type, view_roles, edit_roles,
            created_at
        )
        SELECT
            gen_random_uuid(), p.id, f.id, 'submission_return_review',
            'Revisão do Retorno', 3, 'BLOCKED', 'Sem retorno pendente.',
            'return_review', ARRAY['admin', 'bracvam', 'proponent'],
            ARRAY['proponent'], now()
        FROM process_instances p
        JOIN phases f ON f.process_instance_id = p.id AND f.order_index = 1
        WHERE NOT EXISTS (
            SELECT 1 FROM activity_instances a
            WHERE a.process_instance_id = p.id
              AND a.key = 'submission_return_review'
        )
        """
    )


def downgrade() -> None:
    op.execute(
        'UPDATE audit_events SET activity_run_id = NULL '
        f'WHERE activity_run_id IN ({RETURN_REVIEW_RUNS})'
    )
    op.execute(
        f'DELETE FROM tasks WHERE activity_run_id IN ({RETURN_REVIEW_RUNS})'
    )
    op.execute(
        'DELETE FROM activity_runs WHERE activity_instance_id IN ('
        'SELECT id FROM activity_instances '
        "WHERE key = 'submission_return_review')"
    )
    op.execute(
        "DELETE FROM activity_instances WHERE key = 'submission_return_review'"
    )
