"""Add missing columns to search_sites table

Revision ID: add_search_sites_columns
Revises: merge_heads
Create Date: 2025-11-24

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "add_search_sites_columns"
down_revision: str | None = "add_notification_channels"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add debug_enabled, price_selector, search_url, product_link_selector columns to search_sites."""
    # Add debug_enabled column
    op.add_column(
        "search_sites",
        sa.Column("debug_enabled", sa.Boolean(), server_default="false", nullable=False),
    )
    # Add price_selector column
    op.add_column(
        "search_sites",
        sa.Column("price_selector", sa.String(), nullable=True),
    )
    # Add search_url column
    op.add_column(
        "search_sites",
        sa.Column("search_url", sa.String(), nullable=True),
    )
    # Add product_link_selector column
    op.add_column(
        "search_sites",
        sa.Column("product_link_selector", sa.String(), nullable=True),
    )


def downgrade() -> None:
    """Remove added columns from search_sites."""
    op.drop_column("search_sites", "product_link_selector")
    op.drop_column("search_sites", "search_url")
    op.drop_column("search_sites", "price_selector")
    op.drop_column("search_sites", "debug_enabled")
