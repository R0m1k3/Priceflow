"""Add missing columns to search_sites table

Revision ID: add_search_sites_columns
Revises: add_notification_channels
Create Date: 2025-11-24

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision: str = "add_search_sites_columns"
down_revision: str | None = "add_notification_channels"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def column_exists(table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table."""
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = [col["name"] for col in inspector.get_columns(table_name)]
    return column_name in columns


def upgrade() -> None:
    """Add debug_enabled, price_selector, search_url, product_link_selector columns to search_sites."""
    # Add debug_enabled column (only if not exists)
    if not column_exists("search_sites", "debug_enabled"):
        op.add_column(
            "search_sites",
            sa.Column("debug_enabled", sa.Boolean(), server_default="false", nullable=False),
        )

    # Add price_selector column (only if not exists)
    if not column_exists("search_sites", "price_selector"):
        op.add_column(
            "search_sites",
            sa.Column("price_selector", sa.String(), nullable=True),
        )

    # Add search_url column (only if not exists)
    if not column_exists("search_sites", "search_url"):
        op.add_column(
            "search_sites",
            sa.Column("search_url", sa.String(), nullable=True),
        )

    # Add product_link_selector column (only if not exists)
    if not column_exists("search_sites", "product_link_selector"):
        op.add_column(
            "search_sites",
            sa.Column("product_link_selector", sa.String(), nullable=True),
        )


def downgrade() -> None:
    """Remove added columns from search_sites."""
    if column_exists("search_sites", "product_link_selector"):
        op.drop_column("search_sites", "product_link_selector")
    if column_exists("search_sites", "search_url"):
        op.drop_column("search_sites", "search_url")
    if column_exists("search_sites", "price_selector"):
        op.drop_column("search_sites", "price_selector")
    if column_exists("search_sites", "debug_enabled"):
        op.drop_column("search_sites", "debug_enabled")
