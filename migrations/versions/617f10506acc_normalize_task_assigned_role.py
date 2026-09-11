"""Normalize task assigned_role.

Revision ID: 617f10506acc
Revises: a29d47c1e935

Spec 018 — vocabulário de cargo compartilhado entre `Task.assigned_role` e
`Assignment.role_key`. Migração puramente de dados (nenhum `ALTER TABLE`):
normaliza os três valores hoje gravados em `tasks.assigned_role` para o
vocabulário lowercase já usado por `Assignment.role_key`/`ParticipantRole`,
com `TRIAGE_LEAD`/`BRACVAM_ADMIN` convergindo para o cargo global `bracvam`
(resolvido via `AccessProfile`, não por `Assignment` de processo).
"""

from collections.abc import Sequence

from alembic import op

revision: str = '617f10506acc'
down_revision: str | Sequence[str] | None = 'a29d47c1e935'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "UPDATE tasks SET assigned_role = 'proponent' "
        "WHERE assigned_role = 'PROPONENT'"
    )
    op.execute(
        "UPDATE tasks SET assigned_role = 'bracvam' "
        "WHERE assigned_role = 'TRIAGE_LEAD'"
    )
    op.execute(
        "UPDATE tasks SET assigned_role = 'bracvam' "
        "WHERE assigned_role = 'BRACVAM_ADMIN'"
    )


def downgrade() -> None:
    # `TRIAGE_LEAD` e `BRACVAM_ADMIN` convergiram para o mesmo valor
    # ('bracvam') no upgrade; a reversão não consegue distinguir a origem
    # original de uma linha já normalizada, então recua para `TRIAGE_LEAD`
    # (o cargo global mais comum das duas origens no motor de processos).
    op.execute(
        "UPDATE tasks SET assigned_role = 'PROPONENT' "
        "WHERE assigned_role = 'proponent'"
    )
    op.execute(
        "UPDATE tasks SET assigned_role = 'TRIAGE_LEAD' "
        "WHERE assigned_role = 'bracvam'"
    )
