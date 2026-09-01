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
    permissions = sa.table(
        'permissions',
        sa.column('id', sa.UUID()),
        sa.column('code'),
        sa.column('description'),
    )
    composition = sa.table(
        'access_profile_permissions',
        sa.column('id', sa.UUID()),
        sa.column('profile_id', sa.UUID()),
        sa.column('permission_id', sa.UUID()),
    )
    op.bulk_insert(
        permissions,
        [
            dict(
                id=PERMISSION_ID,
                code=PERMISSION_CODE,
                description=PERMISSION_DESCRIPTION,
            )
        ],
    )
    op.bulk_insert(
        composition,
        [
            dict(
                id=COMPOSITION_ID,
                profile_id=ADMIN_PROFILE_ID,
                permission_id=PERMISSION_ID,
            )
        ],
    )


def downgrade() -> None:
    op.execute(
        'DELETE FROM access_profile_permissions '
        f"WHERE permission_id = '{PERMISSION_ID}'"
    )
    op.execute(f"DELETE FROM permissions WHERE id = '{PERMISSION_ID}'")
