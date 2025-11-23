"""drop notification tables and columns

Revision ID: drop_notifications
Revises: 
Create Date: 2025-11-23

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'drop_notifications'
down_revision = 'add_category_field'  # Points to the last migration
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop foreign key constraint and column from items table
    with op.batch_alter_table('items', schema=None) as batch_op:
        batch_op.drop_constraint('items_notification_profile_id_fkey', type_='foreignkey')
        batch_op.drop_column('notification_profile_id')
    
    # Drop notification_profiles table
    op.drop_table('notification_profiles')


def downgrade() -> None:
    # Recreate notification_profiles table
    op.create_table('notification_profiles',
        sa.Column('id', sa.INTEGER(), nullable=False),
        sa.Column('name', sa.VARCHAR(), nullable=True),
        sa.Column('apprise_url', sa.VARCHAR(), nullable=True),
        sa.Column('notify_on_price_drop', sa.BOOLEAN(), nullable=True),
        sa.Column('notify_on_target_price', sa.BOOLEAN(), nullable=True),
        sa.Column('price_drop_threshold_percent', sa.FLOAT(), nullable=True),
        sa.Column('notify_on_stock_change', sa.BOOLEAN(), nullable=True),
        sa.Column('check_interval_minutes', sa.INTEGER(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Add column back to items table
    with op.batch_alter_table('items', schema=None) as batch_op:
        batch_op.add_column(sa.Column('notification_profile_id', sa.INTEGER(), nullable=True))
        batch_op.create_foreign_key('items_notification_profile_id_fkey', 'notification_profiles', ['notification_profile_id'], ['id'])
