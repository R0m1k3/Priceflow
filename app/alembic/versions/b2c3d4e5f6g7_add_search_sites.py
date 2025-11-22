"""Add search_sites table for product search

Revision ID: b2c3d4e5f6g7
Revises: a1b2c3d4e5f6
Create Date: 2025-11-22 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6g7"
down_revision: str | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create search_sites table for configurable product search sites."""
    op.create_table(
        "search_sites",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("domain", sa.String(), nullable=False, unique=True, index=True),
        sa.Column("logo_url", sa.String(), nullable=True),
        sa.Column("category", sa.String(), nullable=True),
        sa.Column("is_active", sa.Boolean(), default=True),
        sa.Column("priority", sa.Integer(), default=0),
        sa.Column("requires_js", sa.Boolean(), default=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )

    # Insert default popular sites
    op.execute("""
        INSERT INTO search_sites (name, domain, category, is_active, priority, requires_js, created_at, updated_at)
        VALUES
            ('Amazon France', 'amazon.fr', 'Généraliste', true, 1, true, NOW(), NOW()),
            ('Fnac', 'fnac.com', 'Tech / Culture', true, 2, true, NOW(), NOW()),
            ('Cdiscount', 'cdiscount.com', 'Généraliste', true, 3, true, NOW(), NOW()),
            ('Darty', 'darty.com', 'Électroménager', true, 4, true, NOW(), NOW()),
            ('Boulanger', 'boulanger.com', 'Électronique', true, 5, true, NOW(), NOW())
    """)


def downgrade() -> None:
    """Drop search_sites table."""
    op.drop_table("search_sites")
