"""Admin user listing permission.

Revision ID: 7a3e1c9b4d82
Revises: 6f2c9a1d4e70
"""

from collections.abc import Sequence
from uuid import UUID

import sqlalchemy as sa
from alembic import op

revision: str = '7a3e1c9b4d82'
down_revision: str | Sequence[str] | None = '6f2c9a1d4e70'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PERMISSION_ID = UUID('00000000-0000-0000-0000-000000000108')
PERMISSION_CODE = 'users.read'
PERMISSION_DESCRIPTION = 'Consultar contas de usuários.'
ADMIN_PROFILE_ID = UUID('00000000-0000-0000-0000-000000000009')
COMPOSITION_ID = UUID('00000000-0000-0000-0000-000000000208')


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
