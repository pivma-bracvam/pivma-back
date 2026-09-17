"""bracvam_profile_triage_permission

Revision ID: d3f9a1c47b28
Revises: 8b701d7bfeae
Create Date: 2026-09-10

Spec 014 — Semântica BraCVAM e autorização da triagem.
Cria o perfil de acesso ``bracvam`` (distinto de ``management_group`` /
"Grupo Gestor") e a permissão ``triage.review`` (parecer de campo, decisão de
triagem, consulta e feedback da pré-avaliação por IA). Concede ``triage.review``
aos perfis ``bracvam`` e ``administrator``; concede ao ``bracvam`` também
``ai_evaluations.read`` / ``ai_evaluations.manage`` (já existentes) para que a
equipe do BraCVAM configure as avaliações (Spec 013, US1).
"""

from collections.abc import Sequence
from uuid import UUID

import sqlalchemy as sa
from alembic import op

revision: str = 'd3f9a1c47b28'
down_revision: str | Sequence[str] | None = '8b701d7bfeae'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

BRACVAM_PROFILE_ID = UUID('00000000-0000-0000-0000-00000000000a')
ADMIN_PROFILE_ID = UUID('00000000-0000-0000-0000-000000000009')

TRIAGE_REVIEW_ID = UUID('00000000-0000-0000-0000-00000000010c')
AI_EVAL_READ_ID = UUID('00000000-0000-0000-0000-00000000010a')
AI_EVAL_MANAGE_ID = UUID('00000000-0000-0000-0000-00000000010b')

COMP_BRACVAM_TRIAGE_ID = UUID('00000000-0000-0000-0000-00000000020c')
COMP_BRACVAM_AI_READ_ID = UUID('00000000-0000-0000-0000-00000000020d')
COMP_BRACVAM_AI_MANAGE_ID = UUID('00000000-0000-0000-0000-00000000020e')
COMP_ADMIN_TRIAGE_ID = UUID('00000000-0000-0000-0000-00000000020f')

_COMPOSITION_IDS = (
    COMP_BRACVAM_TRIAGE_ID,
    COMP_BRACVAM_AI_READ_ID,
    COMP_BRACVAM_AI_MANAGE_ID,
    COMP_ADMIN_TRIAGE_ID,
)


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
