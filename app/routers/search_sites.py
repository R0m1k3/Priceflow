"""
API Router pour la gestion des sites de recherche
"""

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import SearchSiteCreate, SearchSiteResponse, SearchSiteUpdate
from app.services import search_service
from app.services.search_url_discovery import discover_search_url

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/search-sites", tags=["search-sites"])


@router.get("", response_model=list[SearchSiteResponse])
async def get_all_sites(db: Session = Depends(get_db)):
    """Récupère tous les sites de recherche"""
    sites = search_service.get_all_sites(db)
    return sites


@router.get("/{site_id}", response_model=SearchSiteResponse)
async def get_site(site_id: int, db: Session = Depends(get_db)):
    """Récupère un site par son ID"""
    site = search_service.get_site_by_id(db, site_id)
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    return site


async def _discover_and_update_site(site_id: int, domain: str, db_url: str):
    """Découvre l'URL de recherche en background et met à jour le site"""
    from app.database import SessionLocal

    try:
        logger.info(f"Discovering search URL for site {site_id} ({domain})")
        result = await discover_search_url(domain)

        if result.get("discovered"):
            # Mettre à jour le site avec l'URL découverte
            db = SessionLocal()
            try:
                update_data = {}
                if result.get("search_url"):
                    update_data["search_url"] = result["search_url"]
                if result.get("product_link_selector"):
                    update_data["product_link_selector"] = result["product_link_selector"]

                if update_data:
                    search_service.update_site(db, site_id, update_data)
                    logger.info(f"Updated site {site_id} with discovered URL: {result.get('search_url')}")
            finally:
                db.close()
        else:
            logger.warning(f"Could not discover search URL for {domain}")

    except Exception as e:
        logger.error(f"Error in background discovery for {domain}: {e}")


@router.post("", response_model=SearchSiteResponse, status_code=201)
async def create_site(
    site: SearchSiteCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Crée un nouveau site de recherche.
    Si search_url n'est pas fourni, tente de le découvrir automatiquement.
    """
    try:
        new_site = search_service.create_site(db, site.model_dump())

        # Si pas de search_url, lancer la découverte en background
        if not site.search_url:
            import os
            db_url = os.getenv("DATABASE_URL", "")
            background_tasks.add_task(
                _discover_and_update_site,
                new_site.id,
                new_site.domain,
                db_url,
            )
            logger.info(f"Started background discovery for site {new_site.id}")

        return new_site
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{site_id}", response_model=SearchSiteResponse)
async def update_site(
    site_id: int,
    site: SearchSiteUpdate,
    db: Session = Depends(get_db),
):
    """Met à jour un site de recherche"""
    updated = search_service.update_site(
        db, site_id, site.model_dump(exclude_unset=True)
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Site not found")
    return updated


@router.delete("/{site_id}", status_code=204)
async def delete_site(site_id: int, db: Session = Depends(get_db)):
    """Supprime un site de recherche"""
    deleted = search_service.delete_site(db, site_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Site not found")
    return None


@router.post("/{site_id}/discover", response_model=dict)
async def discover_site_search_url(
    site_id: int,
    db: Session = Depends(get_db),
):
    """
    Force la découverte de l'URL de recherche pour un site existant.
    Utile si la découverte automatique n'a pas fonctionné.
    """
    site = search_service.get_site_by_id(db, site_id)
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")

    result = await discover_search_url(site.domain)

    if result.get("discovered"):
        # Mettre à jour le site
        update_data = {}
        if result.get("search_url"):
            update_data["search_url"] = result["search_url"]
        if result.get("product_link_selector"):
            update_data["product_link_selector"] = result["product_link_selector"]

        if update_data:
            search_service.update_site(db, site_id, update_data)

        return {
            "success": True,
            "message": f"URL de recherche découverte: {result.get('search_url')}",
            "search_url": result.get("search_url"),
            "product_link_selector": result.get("product_link_selector"),
        }
    else:
        return {
            "success": False,
            "message": "Impossible de découvrir l'URL de recherche automatiquement",
        }
