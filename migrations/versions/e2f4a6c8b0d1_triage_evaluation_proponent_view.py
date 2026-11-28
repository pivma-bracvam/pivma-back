"""Proponent views the triage of existing processes (Spec 049).

Adds `proponent` to `view_roles` of every `triage_evaluation` instance that
lacks it, matching the new template versions. `edit_roles` is untouched.
The downgrade removes the grant. It does not unpublish the new template
versions, as in the earlier template bumps: processes created after a
downgrade still get the grant from the published version.

Revision ID: e2f4a6c8b0d1
Revises: b7d3e9a1c5f2
"""

from collections.abc import Sequence

from alembic import op

revision: str = 'e2f4a6c8b0d1'
down_revision: str | Sequence[str] | None = 'b7d3e9a1c5f2'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        'UPDATE activity_instances '
        "SET view_roles = array_append(view_roles, 'proponent') "
        "WHERE key = 'triage_evaluation' "
        "AND NOT ('proponent' = ANY(view_roles))"
    )


def downgrade() -> None:
    op.execute(
        'UPDATE activity_instances '
        "SET view_roles = array_remove(view_roles, 'proponent') "
        "WHERE key = 'triage_evaluation'"
    )
