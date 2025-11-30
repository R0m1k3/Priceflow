"""
API Router pour la gestion des sites de recherche
Les sites sont configurés en dur dans direct_search_service.py
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import SearchSiteResponse, SearchSiteUpdate
from app.services import search_service

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


@router.put("/{site_id}", response_model=SearchSiteResponse)
async def update_site(
    site_id: int,
    site: SearchSiteUpdate,
    db: Session = Depends(get_db),
):
    """
    Met à jour un site de recherche.
    Permet uniquement de modifier is_active et priority.
    """
    # Limiter les champs modifiables
    allowed_fields = {"is_active", "priority"}
    update_data = site.model_dump(exclude_unset=True)
    filtered_data = {k: v for k, v in update_data.items() if k in allowed_fields}

    if not filtered_data:
        raise HTTPException(
            status_code=400,
            detail="Seuls les champs 'is_active' et 'priority' peuvent être modifiés"
        )

    updated = search_service.update_site(db, site_id, filtered_data)
    if not updated:
        raise HTTPException(status_code=404, detail="Site not found")
    return updated


@router.post("/seed", response_model=dict)
async def seed_default_sites(db: Session = Depends(get_db)):
    """
    Initialise les sites par défaut s'ils n'existent pas encore.
    Utile après une première installation.
    """
    created = search_service.seed_default_sites(db)
    total = len(search_service.get_all_sites(db))

    return {
        "success": True,
        "message": f"{created} nouveau(x) site(s) créé(s)",
        "sites_created": created,
        "total_sites": total,
    }


@router.post("/reset", response_model=dict)
async def reset_sites_to_defaults(db: Session = Depends(get_db)):
    """
    Réinitialise tous les sites avec les valeurs par défaut.
    ATTENTION: Supprime tous les sites existants et recrée à partir de la config.
    """
    created = search_service.reset_sites_to_defaults(db)

    return {
        "success": True,
        "message": f"Sites réinitialisés. {created} site(s) créé(s)",
        "sites_created": created,
    }
