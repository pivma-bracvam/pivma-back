"""Merge notifications (Spec 036, #67) and per laboratory runs (#68).

The two revisions branched from cc6c65843305 and left two heads. This
revision only joins them; it changes no schema.

Revision ID: 5af69c71be3c
Revises: 6eb1ae208b7d, b7d3e9a1c204
"""

from collections.abc import Sequence

revision: str = '5af69c71be3c'
down_revision: str | Sequence[str] | None = ('6eb1ae208b7d', 'b7d3e9a1c204')
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
