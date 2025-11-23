"""add_is_available_to_items

Revision ID: add_is_available
Revises: 
Create Date: 2025-11-23

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_is_available'
down_revision = None  # Update this if there are previous migrations
branch_labels = None
depends_on = None


def upgrade():
    # Add is_available column to items table
    op.add_column('items', sa.Column('is_available', sa.Boolean(), nullable=True, server_default='true'))


def downgrade():
    # Remove is_available column from items table
    op.drop_column('items', 'is_available')
