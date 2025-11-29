"""Add catalog module tables

Revision ID: c1d2e3f4g5h6
Revises: b2c3d4e5f6g7
Create Date: 2025-11-29 18:56:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c1d2e3f4g5h6"
down_revision: str | None = "b2c3d4e5f6g7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create tables for the catalog module."""
    
    # Create enseignes table
    op.create_table(
        "enseignes",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("nom", sa.String(), nullable=False),
        sa.Column("slug_bonial", sa.String(), nullable=False, unique=True, index=True),
        sa.Column("logo_url", sa.String(), nullable=True),
        sa.Column("couleur", sa.String(), nullable=False),
        sa.Column("site_url", sa.String(), nullable=True),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("is_active", sa.Boolean(), default=True),
        sa.Column("ordre_affichage", sa.Integer(), default=0),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    
    # Create catalogues table
    op.create_table(
        "catalogues",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("enseigne_id", sa.Integer(), sa.ForeignKey("enseignes.id"), nullable=False, index=True),
        sa.Column("titre", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("date_debut", sa.DateTime(), nullable=False, index=True),
        sa.Column("date_fin", sa.DateTime(), nullable=False, index=True),
        sa.Column("image_couverture_url", sa.String(), nullable=False),
        sa.Column("catalogue_url", sa.String(), nullable=False),
        sa.Column("nombre_pages", sa.Integer(), default=0),
        sa.Column("statut", sa.String(), default="actif", index=True),
        sa.Column("content_hash", sa.String(64), nullable=False, unique=True, index=True),
        sa.Column("metadonnees", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    
    # Create catalogue_pages table
    op.create_table(
        "catalogue_pages",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("catalogue_id", sa.Integer(), sa.ForeignKey("catalogues.id"), nullable=False, index=True),
        sa.Column("numero_page", sa.Integer(), nullable=False),
        sa.Column("image_url", sa.String(), nullable=False),
        sa.Column("image_thumbnail_url", sa.String(), nullable=True),
        sa.Column("largeur", sa.Integer(), nullable=True),
        sa.Column("hauteur", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    
    # Create unique index on catalogue_id + numero_page
    op.create_index(
        "idx_catalogue_page_numero",
        "catalogue_pages",
        ["catalogue_id", "numero_page"],
        unique=True,
    )
    
    # Create scraping_logs table
    op.create_table(
        "scraping_logs",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("date_execution", sa.DateTime(), nullable=True, index=True),
        sa.Column("enseigne_id", sa.Integer(), sa.ForeignKey("enseignes.id"), nullable=True),
        sa.Column("statut", sa.String(), nullable=False),
        sa.Column("catalogues_trouves", sa.Integer(), default=0),
        sa.Column("catalogues_nouveaux", sa.Integer(), default=0),
        sa.Column("catalogues_mis_a_jour", sa.Integer(), default=0),
        sa.Column("duree_secondes", sa.Float(), nullable=True),
        sa.Column("message_erreur", sa.Text(), nullable=True),
        sa.Column("details", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    """Drop catalog module tables."""
    op.drop_table("scraping_logs")
    op.drop_index("idx_catalogue_page_numero", table_name="catalogue_pages")
    op.drop_table("catalogue_pages")
    op.drop_table("catalogues")
    op.drop_table("enseignes")
