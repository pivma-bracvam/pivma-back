"""add_ai_fields_to_form_fields

Revision ID: 62eee61a6ad3
Revises: 3b75cf649c4e
Create Date: 2026-09-09 04:57:07.319190

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '62eee61a6ad3'
down_revision: Union[str, Sequence[str], None] = '3b75cf649c4e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


from sqlalchemy.dialects import postgresql


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'form_fields',
        sa.Column('ai_evaluation_enabled', sa.Boolean(), nullable=False, server_default=sa.text('false')),
    )
    op.add_column(
        'form_fields',
        sa.Column('ai_context_instructions', sa.Text(), nullable=True),
    )
    op.add_column(
        'form_fields',
        sa.Column('ai_validation_rules', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('form_fields', 'ai_validation_rules')
    op.drop_column('form_fields', 'ai_context_instructions')
    op.drop_column('form_fields', 'ai_evaluation_enabled')
