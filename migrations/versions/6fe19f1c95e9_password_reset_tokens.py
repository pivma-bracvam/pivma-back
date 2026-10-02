"""Password reset tokens (Spec 039).

Creates the password_reset_tokens table. Only the SHA-256 hash of each token
is stored. Existing data is untouched.

Revision ID: 6fe19f1c95e9
Revises: 5af69c71be3c
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '6fe19f1c95e9'
down_revision: str | Sequence[str] | None = '5af69c71be3c'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = 'password_reset_tokens'


def upgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column(
            'user_id',
            sa.UUID(),
            sa.ForeignKey('users.id', name=f'fk_{TABLE}_user_id'),
            nullable=False,
        ),
        sa.Column('token_hash', sa.String(64), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('used_at', sa.DateTime(), nullable=True),
        sa.Column(
            'created_at',
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        *(
            sa.Column(
                column,
                sa.UUID(),
                sa.ForeignKey('users.id', name=f'fk_{TABLE}_{column}'),
                nullable=True,
            )
            for column in ('created_by', 'updated_by', 'deleted_by')
        ),
    )
    op.create_index(
        'uq_password_reset_tokens_token_hash',
        TABLE,
        ['token_hash'],
        unique=True,
    )
    op.create_index('ix_password_reset_tokens_user_id', TABLE, ['user_id'])


def downgrade() -> None:
    op.drop_index('ix_password_reset_tokens_user_id', table_name=TABLE)
    op.drop_index('uq_password_reset_tokens_token_hash', table_name=TABLE)
    op.drop_table(TABLE)
