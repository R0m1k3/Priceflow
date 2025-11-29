"""Merge catalog module with existing heads

Revision ID: d2e3f4g5h6i7
Revises: c1d2e3f4g5h6, add_notification_channels
Create Date: 2025-11-29 19:30:00.000000

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd2e3f4g5h6i7'
down_revision: tuple[str, str] = ('c1d2e3f4g5h6', 'add_notification_channels')
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # No schema changes needed - this is just a merge migration
    pass


def downgrade() -> None:
    # No schema changes needed - this is just a merge migration
    pass
