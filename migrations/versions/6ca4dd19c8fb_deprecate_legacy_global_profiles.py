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
    pass


def downgrade() -> None:
    pass
