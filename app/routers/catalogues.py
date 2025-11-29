"""
API Router for catalog module
Endpoints for enseignes, catalogues, and admin operations
"""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from playwright.async_api import async_playwright

from app.database import get_db
from app.models import Enseigne, Catalogue, CataloguePage, ScrapingLog, User
from app.dependencies import get_current_user
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
    
    return CatalogueDetailResponse.model_validate(catalogue)


@router.get("/{catalogue_id}/pages", response_model=list[CataloguePageResponse])
async def get_catalogue_pages(
    catalogue_id: int,
    db: Session = Depends(get_db),
):
    """Get all pages for a specific catalogue"""
    catalogue = db.query(Catalogue).filter(Catalogue.id == catalogue_id).first()
    
    if not catalogue:
        raise HTTPException(status_code=404, detail="Catalogue not found")
    
    pages = (
        db.query(CataloguePage)
        .filter(CataloguePage.catalogue_id == catalogue_id)
        .order_by(CataloguePage.numero_page)
        .all()
    )
    
    return [CataloguePageResponse.model_validate(page) for page in pages]


# === Admin Endpoints ===

@router.get("/admin/stats", response_model=ScrapingStatsResponse)
async def get_scraping_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get scraping statistics"""
    total_catalogues = db.query(func.count(Catalogue.id)).scalar()
    
    # Catalogues par enseigne
    catalogues_par_enseigne = {}
    enseignes = db.query(Enseigne).all()
    for enseigne in enseignes:
        count = (
            db.query(func.count(Catalogue.id))
            .filter(Catalogue.enseigne_id == enseigne.id)
            .scalar()
        )
        catalogues_par_enseigne[enseigne.nom] = count
    
    # Last scraping
    last_scraping = (
        db.query(ScrapingLog)
        .order_by(ScrapingLog.date_execution.desc())
        .first()
    )
    
    return ScrapingStatsResponse(
        total_catalogues=total_catalogues,
        catalogues_par_enseigne=catalogues_par_enseigne,
        derniere_mise_a_jour=last_scraping.date_execution if last_scraping else None,
        prochaine_execution="6h00 et 18h00",
    )


@router.get("/admin/scraping/logs", response_model=list[ScrapingLogResponse])
async def get_scraping_logs(
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get scraping logs"""
    logs = (
        db.query(ScrapingLog)
        .order_by(ScrapingLog.date_execution.desc())
        .limit(limit)
        .all()
    )
    
    return [ScrapingLogResponse.model_validate(log) for log in logs]


@router.post("/admin/scraping/trigger")
async def trigger_scraping(
    enseigne_id: int | None = Query(None, description="Optional: specific enseigne ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Trigger manual scraping"""
    if enseigne_id:
        enseigne = db.query(Enseigne).filter(Enseigne.id == enseigne_id).first()
        if not enseigne:
            raise HTTPException(status_code=404, detail="Enseigne not found")
        
        async with async_playwright() as p:
            import os
            browserless_url = os.environ.get("BROWSERLESS_URL", "ws://browserless:3000")
            browser = await p.chromium.connect_over_cdp(browserless_url)
            log = await scrape_enseigne(enseigne, db, browser)
            await browser.close()
        
        return {
            "message": f"Scraping completed for {enseigne.nom}",
            "catalogues_trouves": log.catalogues_trouves,
            "catalogues_nouveaux": log.catalogues_nouveaux,
        }
    else:
        logs = await scrape_all_enseignes(db)
        total_nouveaux = sum(log.catalogues_nouveaux for log in logs)
        
        return {
            "message": f"Scraping completed for all enseignes",
            "catalogues_nouveaux": total_nouveaux,
        }


@router.post("/admin/cleanup")
async def cleanup_catalogs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete invalid catalogs (0 pages or generic titles)"""
    if not current_user.is_admin:
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
