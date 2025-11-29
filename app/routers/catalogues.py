"""
API Router for catalog module
Endpoints for enseignes, catalogues, and admin operations
"""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from app.database import get_db
from app.models import Enseigne, Catalogue, CataloguePage, ScrapingLog
from app.schemas_catalogues import (
    EnseigneResponse,
    CatalogueListResponse,
    CatalogueDetailResponse,
    CataloguePageResponse,
    CataloguesPaginatedResponse,
    PaginationMeta,
    ScrapingLogResponse,
    ScrapingStatsResponse,
)
from app.services.bonial_scraper import scrape_all_enseignes, scrape_enseigne

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/catalogues", tags=["catalogues"])


# === Enseignes Endpoints ===

@router.get("/enseignes", response_model=list[EnseigneResponse])
async def get_enseignes(
    db: Session = Depends(get_db),
):
    """Get all active enseignes with catalog counts"""
    enseignes = (
        db.query(Enseigne)
        .filter(Enseigne.is_active == True)
        .order_by(Enseigne.ordre_affichage)
        .all()
    )
    
    # Add catalog counts
    result = []
    for enseigne in enseignes:
        count = (
            db.query(func.count(Catalogue.id))
            .filter(
                and_(
                    Catalogue.enseigne_id == enseigne.id,
                    Catalogue.statut == "actif"
                )
            )
            .scalar()
        )
        
        enseigne_data = EnseigneResponse.model_validate(enseigne)
        enseigne_data.catalogues_actifs_count = count
        result.append(enseigne_data)
    
    return result


# === Catalogues Endpoints ===

@router.get("", response_model=CataloguesPaginatedResponse)
async def get_catalogues(
    enseigne_ids: str | None = Query(None, description="Comma-separated enseigne IDs"),
    statut: str | None = Query(None, description="Filter by status: actif, termine, erreur, tous"),
    date_debut_min: datetime | None = Query(None, description="Start date minimum"),
    date_fin_max: datetime | None = Query(None, description="End date maximum"),
    recherche: str | None = Query(None, description="Search in titles"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    sort: str = Query("date_debut", description="Sort by: date_debut, date_fin, enseigne"),
    order: str = Query("desc", description="Order: asc, desc"),
    db: Session = Depends(get_db),
):
    """Get catalogues with filters and pagination"""
    
    # Build query
    query = db.query(Catalogue)
    
    # Filter by enseignes
    if enseigne_ids:
        try:
            ids = [int(id_str.strip()) for id_str in enseigne_ids.split(",")]
            query = query.filter(Catalogue.enseigne_id.in_(ids))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid enseigne_ids format")
    
    # Filter by status
    if statut and statut != "tous":
        query = query.filter(Catalogue.statut == statut)
    
    # Filter by dates
    if date_debut_min:
        query = query.filter(Catalogue.date_debut >= date_debut_min)
    if date_fin_max:
        query = query.filter(Catalogue.date_fin <= date_fin_max)
    
    # Search in titles
    if recherche:
        query = query.filter(Catalogue.titre.ilike(f"%{recherche}%"))
    
    # Sort
    sort_column = {
        "date_debut": Catalogue.date_debut,
        "date_fin": Catalogue.date_fin,
        "enseigne": Catalogue.enseigne_id,
    }.get(sort, Catalogue.date_debut)
    
    if order == "desc":
        query = query.order_by(sort_column.desc())
    else:
        query = query.order_by(sort_column.asc())
    
    # Count total
    total = query.count()
    
    # Paginate
    offset = (page - 1) * limit
    catalogues = query.offset(offset).limit(limit).all()
    
    # Build response
    data = []
    for catalogue in catalogues:
        cat_response = CatalogueListResponse.model_validate(catalogue)
        data.append(cat_response)
    
    pagination = PaginationMeta(
        total=total,
        page=page,
        limit=limit,
        pages_total=(total + limit - 1) // limit,
    )
    
    # Get last scraping time
    last_scraping = (
        db.query(ScrapingLog)
        .order_by(ScrapingLog.date_execution.desc())
        .first()
    )
    
    metadata = {
        "derniere_mise_a_jour": last_scraping.date_execution if last_scraping else None
    }
    
    return CataloguesPaginatedResponse(
        data=data,
        pagination=pagination,
        metadata=metadata,
    )


@router.get("/{catalogue_id}", response_model=CatalogueDetailResponse)
async def get_catalogue_detail(
    catalogue_id: int,
    db: Session = Depends(get_db),
):
    """Get detailed information for a specific catalogue"""
    catalogue = db.query(Catalogue).filter(Catalogue.id == catalogue_id).first()
    
    if not catalogue:
        raise HTTPException(status_code=404, detail="Catalogue not found")
    
        raise HTTPException(status_code=403, detail="Not authorized")
    
    deleted_count = 0
    
    # 1. Delete catalogs with 0 pages
    bad_catalogs = db.query(Catalogue).filter(Catalogue.nombre_pages == 0).all()
    for cat in bad_catalogs:
        db.delete(cat)
        deleted_count += 1
    
    # 2. Delete generic titles
    generic_titles = [
        "Restez informé",
        "Catalogues Bazar",
        "Toutes les offres",
        "Voir les offres",
        "Téléchargez l'application",
        "Newsletter",
        "BLACK FRIDAY"
    ]
    
    for title_part in generic_titles:
        generic_cats = db.query(Catalogue).filter(Catalogue.titre.ilike(f"%{title_part}%")).all()
        for cat in generic_cats:
            # Only delete if it has few pages (e.g. < 2) to be safe
            if cat.nombre_pages < 2:
                db.delete(cat)
                deleted_count += 1
    
    db.commit()
    logger.info(f"Cleanup: deleted {deleted_count} invalid catalogs")
    
    return {"message": f"Cleanup complete. Deleted {deleted_count} invalid catalogs."}
