"""add_category_to_items

Revision ID: add_category_field
Revises: add_is_available
Create Date: 2025-11-23

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_category_field'
down_revision = 'add_is_available'
branch_labels = None
depends_on = None


def upgrade():
    # Add category column to items table
    op.add_column('items', sa.Column('category', sa.String(255), nullable=True))


def downgrade():
    # Remove category column from items table
    op.drop_column('items', 'category')
