"""add notification channels

Revision ID: add_notification_channels
Revises: merge_heads
Create Date: 2025-11-23

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_notification_channels'
down_revision = 'merge_heads'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create notification_channels table
    op.create_table('notification_channels',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('type', sa.String(), nullable=False),
        sa.Column('configuration', sa.Text(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_notification_channels_id'), 'notification_channels', ['id'], unique=False)

    # Add notification_channel_id to items table
    op.add_column('items', sa.Column('notification_channel_id', sa.Integer(), nullable=True))
    op.create_foreign_key(None, 'items', 'notification_channels', ['notification_channel_id'], ['id'])


def downgrade() -> None:
    # Remove foreign key and column from items table
    op.drop_constraint(None, 'items', type_='foreignkey')
    op.drop_column('items', 'notification_channel_id')

    # Drop notification_channels table
    op.drop_index(op.f('ix_notification_channels_id'), table_name='notification_channels')
    op.drop_table('notification_channels')
