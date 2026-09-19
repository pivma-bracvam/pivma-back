"""form_templates_manage_permission

Revision ID: fa506675d3f9
Revises: 6ca4dd19c8fb
Create Date: 2026-09-17

Issue #39 — Fecha a escalada de privilégio em `can_manage_process_templates`
(que aceitava `rbac.read`, uma permissão de leitura, e qualquer perfil
nomeado literalmente "Administrador" como prova de admin). A correção exige
uma permissão discreta e legítima para que a equipe BraCVAM continue
editando formulários (adicionar/ajustar campos) — necessidade de negócio
real, hoje só satisfeita através da própria brecha combinada com o
mecanismo dinâmico da Spec 023 (`effective_permission_codes`:
Administrador e BraCVAM cobrem toda `Permission` ativa do catálogo,
presente e futura, sem precisar de composição explícita — ver
`core/authorization.py`). Por isso esta migração só insere a permissão
``form_templates.manage`` no catálogo: nenhuma linha de
`access_profile_permissions` é necessária para que Administrador e
BraCVAM já a tenham — compor explicitamente duplicaria o que a Spec 023 já
garante dinamicamente (confirmado por
`tests/integration/migrations/test_bracvam_rbac_migration.py`, que trava o
conjunto exato de composições explícitas do catálogo).
"""

from collections.abc import Sequence
from uuid import UUID

import sqlalchemy as sa
from alembic import op

revision: str = 'fa506675d3f9'
down_revision: str | Sequence[str] | None = '6ca4dd19c8fb'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

FORM_TEMPLATES_MANAGE_ID = UUID('00000000-0000-0000-0000-00000000010d')


def upgrade() -> None:
    permissions = sa.table(
        'permissions',
        sa.column('id', sa.Uuid()),
        sa.column('code'),
        sa.column('description'),
    )
    op.bulk_insert(
        permissions,
        [
            dict(
                id=FORM_TEMPLATES_MANAGE_ID,
                code='form_templates.manage',
                description=(
                    'Gerir a definição de formulários de processo '
                    '(campos, nome, descrição).'
                ),
            )
        ],
    )


def downgrade() -> None:
    op.execute(
        f"DELETE FROM permissions WHERE id = '{FORM_TEMPLATES_MANAGE_ID}'"
    )
