"""User management permission.

Revision ID: 8c5e7a1b9d02
Revises: 7b4f5d6e8a90
"""

from collections.abc import Sequence
from uuid import UUID

import sqlalchemy as sa
from alembic import op

revision: str = '8c5e7a1b9d02'
down_revision: str | Sequence[str] | None = '7b4f5d6e8a90'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PERMISSION_ID = UUID('00000000-0000-0000-0000-000000000109')
PERMISSION_CODE = 'users.manage'
PERMISSION_DESCRIPTION = 'Atualizar dados administrativos de usuários.'
ADMIN_PROFILE_ID = UUID('00000000-0000-0000-0000-000000000009')
COMPOSITION_ID = UUID('00000000-0000-0000-0000-000000000209')


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
