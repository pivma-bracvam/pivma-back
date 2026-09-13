"""deprecate_legacy_global_profiles

Revision ID: 6ca4dd19c8fb
Revises: 617f10506acc
Create Date: 2026-09-13

Spec 023 — Simplificação de cargos globais (RBAC). Os únicos perfis globais
atribuíveis passam a ser Administrador e BraCVAM (Padrão = ausência de
perfil). Os 8 perfis abaixo nunca tiveram nenhuma ``Permission`` vinculada
(confirmado nas migrations ``c1e4a9f8b312`` e ``d3f9a1c47b28``) e são
descontinuados: soft-delete do próprio perfil e de qualquer
``UserAccessProfile`` ativo que o referencie. Nenhuma linha é removida
fisicamente; o histórico em ``rbac_changes`` permanece intacto.
"""

from collections.abc import Sequence

from alembic import op

revision: str = '6ca4dd19c8fb'
down_revision: str | Sequence[str] | None = '617f10506acc'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DEPRECATED_SYSTEM_KEYS = (
    'management_group',
    'study_manager',
    'participating_laboratory',
    'ad_hoc_evaluator',
    'reviewer',
    'specialist',
    'statistical_analyst',
    'proponent',
)


def upgrade() -> None:
    keys = "', '".join(DEPRECATED_SYSTEM_KEYS)
    op.execute(
        'UPDATE access_profiles SET deleted_at = now() '
        f"WHERE system_key IN ('{keys}') AND deleted_at IS NULL"
    )
    op.execute(
        'UPDATE user_access_profiles SET deleted_at = now() '
        'WHERE deleted_at IS NULL AND profile_id IN ('
        f"SELECT id FROM access_profiles WHERE system_key IN ('{keys}')"
        ')'
    )


def downgrade() -> None:
    keys = "', '".join(DEPRECATED_SYSTEM_KEYS)
    op.execute(
        'UPDATE user_access_profiles SET deleted_at = NULL '
        'WHERE profile_id IN ('
        f"SELECT id FROM access_profiles WHERE system_key IN ('{keys}')"
        ')'
    )
    op.execute(
        'UPDATE access_profiles SET deleted_at = NULL '
        f"WHERE system_key IN ('{keys}')"
    )
