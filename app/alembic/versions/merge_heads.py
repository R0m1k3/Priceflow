"""merge multiple heads

Revision ID: merge_heads
Revises: drop_notifications, performance_indexes_v2
Create Date: 2025-11-23

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'merge_heads'
down_revision = ('drop_notifications', 'performance_indexes_v2')
branch_labels = None
depends_on = None


def upgrade() -> None:
    # No changes needed, this is just a merge revision
    pass


def downgrade() -> None:
    # No changes needed, this is just a merge revision
    pass
