"""merge search and catalog

Revision ID: merge_search_and_catalog
Revises: add_search_sites_columns, d2e3f4g5h6i7
Create Date: 2025-11-30 23:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'merge_search_and_catalog'
down_revision = ('add_search_sites_columns', 'd2e3f4g5h6i7')
branch_labels = None
depends_on = None

def upgrade() -> None:
    pass

def downgrade() -> None:
    pass
