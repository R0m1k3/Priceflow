"""
API Router pour la gestion des sites de recherche
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import SearchSiteCreate, SearchSiteResponse, SearchSiteUpdate
from app.services import search_service

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


@router.post("", response_model=SearchSiteResponse, status_code=201)
async def create_site(site: SearchSiteCreate, db: Session = Depends(get_db)):
    """Crée un nouveau site de recherche"""
    try:
        new_site = search_service.create_site(db, site.model_dump())
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
