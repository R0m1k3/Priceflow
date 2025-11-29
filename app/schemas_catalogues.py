"""
Pydantic schemas for catalog module API
"""

from datetime import datetime
from pydantic import BaseModel


# === Enseigne Schemas ===

class EnseigneResponse(BaseModel):
    id: int
    nom: str
    slug_bonial: str
    logo_url: str | None
    couleur: str
    site_url: str | None
    description: str | None
    is_active: bool
    ordre_affichage: int
    
    # Statistics
    catalogues_actifs_count: int | None = None
    
    model_config = {"from_attributes": True}


# === Catalogue Schemas ===

class CatalogueListResponse(BaseModel):
    id: int
    enseigne: EnseigneResponse
    titre: str
    date_debut: datetime
    date_fin: datetime
    image_couverture_url: str
    statut: str
    nombre_pages: int
    created_at: datetime
    
    model_config = {"from_attributes": True}


class CatalogueDetailResponse(BaseModel):
    id: int
    enseigne: EnseigneResponse
    titre: str
    description: str | None
    date_debut: datetime
    date_fin: datetime
    image_couverture_url: str
    catalogue_url: str
    statut: str
    nombre_pages: int
    metadonnees: str | None
    created_at: datetime
    updated_at: datetime
    
    model_config = {"from_attributes": True}


class CataloguePageResponse(BaseModel):
    id: int
    numero_page: int
    image_url: str
    image_thumbnail_url: str | None
    largeur: int | None
    hauteur: int | None
    
    model_config = {"from_attributes": True}


# === Pagination ===

class PaginationMeta(BaseModel):
    total: int
    page: int
    limit: int
    pages_total: int


class CataloguesPaginatedResponse(BaseModel):
    data: list[CatalogueListResponse]
    pagination: PaginationMeta
    metadata: dict


# === Admin Schemas ===

class ScrapingLogResponse(BaseModel):
    id: int
    date_execution: datetime
    enseigne_id: int | None
    enseigne_nom: str | None
    statut: str
    catalogues_trouves: int
    catalogues_nouveaux: int
    catalogues_mis_a_jour: int
    duree_secondes: float | None
    message_erreur: str | None
    
    model_config = {"from_attributes": True}


class ScrapingStatsResponse(BaseModel):
    total_catalogues: int
    catalogues_par_enseigne: dict[str, int]
    derniere_mise_a_jour: datetime | None
    prochaine_execution: str | None
