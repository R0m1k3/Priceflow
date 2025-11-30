"""
API Router pour la recherche de produits
Utilise Server-Sent Events (SSE) pour le streaming des résultats
"""

import json
import logging

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.services import improved_search_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/search", tags=["search"])


@router.get("")
async def search_products(
    q: str = Query(..., min_length=1, description="Terme de recherche"),
    sites: str | None = Query(None, description="IDs des sites, séparés par virgule"),
    max_results: int = Query(20, ge=1, le=50, description="Nombre max de résultats"),
    db: Session = Depends(get_db),
):
    """
    Recherche des produits sur les sites configurés.

    Retourne un flux SSE avec les résultats au fur et à mesure.

    Format des événements SSE:
    - event: progress
    - data: {"status": "...", "total": N, "completed": N, "results": [...]}
    """
    # Parser les IDs de sites
    site_ids = None
    if sites:
        try:
            site_ids = [int(s.strip()) for s in sites.split(",") if s.strip()]
        except ValueError:
            site_ids = None

    async def generate():
        try:
            async for progress in improved_search_service.search_products(
                query=q,
                db=db,
                site_ids=site_ids,
                max_results=max_results,
            ):
                # Format SSE
                data = progress.model_dump_json()
                yield f"event: progress\ndata: {data}\n\n"

        except Exception as e:
            logger.error(f"Erreur recherche: {e}")
            error_data = json.dumps({
                "status": "error",
                "total": 0,
                "completed": 0,
                "message": str(e),
                "results": [],
            })
            yield f"event: progress\ndata: {error_data}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/health")
async def search_health():
    """Vérifie que le service de recherche est opérationnel"""
    from app.services import searxng_service

    searxng_ok = await searxng_service.health_check()

    return {
        "status": "ok" if searxng_ok else "degraded",
        "searxng": "ok" if searxng_ok else "unavailable",
    }
