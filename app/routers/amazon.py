"""
API Router pour la recherche Amazon France
Utilise Server-Sent Events (SSE) pour le streaming des résultats
"""

import json
import logging
from typing import AsyncGenerator

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.services.amazon_scraper import scrape_amazon_search, AmazonProduct

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/amazon", tags=["amazon"])


class AmazonSearchProgress(BaseModel):
    """Progress model for SSE streaming"""
    status: str  # 'searching', 'completed', 'error'
    total: int
    completed: int
    message: str
    results: list[dict]


@router.get("/search")
async def search_amazon(
    q: str = Query(..., min_length=1, description="Terme de recherche"),
    max_results: int = Query(20, ge=1, le=50, description="Nombre max de résultats"),
):
    """
    Recherche de produits sur Amazon France.

    Retourne un flux SSE avec les résultats.

    Format des événements SSE:
    - event: progress
    - data: {"status": "...", "total": 1, "completed": 0/1, "results": [...]}
    """

    async def generate() -> AsyncGenerator[str, None]:
        try:
            # Initial progress
            progress = AmazonSearchProgress(
                status="searching",
                total=1,
                completed=0,
                message=f"Recherche sur Amazon France: '{q}'...",
                results=[]
            )
            yield f"event: progress\ndata: {progress.model_dump_json()}\n\n"

            # Execute search
            logger.info(f"Starting Amazon search for: {q}")
            products = await scrape_amazon_search(q, max_results=max_results)

            # Convert to dict
            results = [p.model_dump() for p in products]

            # Final progress
            if results:
                progress = AmazonSearchProgress(
                    status="completed",
                    total=1,
                    completed=1,
                    message=f"✅ {len(results)} produits trouvés",
                    results=results
                )
            else:
                progress = AmazonSearchProgress(
                    status="completed",
                    total=1,
                    completed=1,
                    message="Aucun produit trouvé",
                    results=[]
                )

            yield f"event: progress\ndata: {progress.model_dump_json()}\n\n"

        except Exception as e:
            logger.error(f"Error during Amazon search: {e}", exc_info=True)
            error_progress = AmazonSearchProgress(
                status="error",
                total=1,
                completed=1,
                message=f"Erreur: {str(e)}",
                results=[]
            )
            yield f"event: progress\ndata: {error_progress.model_dump_json()}\n\n"

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
async def amazon_health():
    """Vérifie que le service Amazon est opérationnel"""
    return {
        "status": "ok",
        "service": "Amazon France Scraper",
        "anti_detection": "enabled",
        "features": [
            "User-Agent rotation",
            "Proxy rotation (10 proxies)",
            "Random delays",
            "Realistic headers",
            "Crawl4AI anti-detection"
        ]
    }
