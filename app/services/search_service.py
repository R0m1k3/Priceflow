"""
Search Service - Orchestrateur de recherche de produits
Combine SearXNG + Light Scraper + Browserless fallback
"""

import asyncio
import logging
from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy.orm import Session

from app.models import SearchSite
from app.schemas import SearchProgress, SearchResultItem
from app.services import ai_service, light_scraper_service, searxng_service
from app.services.scraper_service import ScraperService
from app.services.settings_service import SettingsService

logger = logging.getLogger(__name__)

# Configuration par défaut
DEFAULT_MAX_RESULTS = 20
DEFAULT_PARALLEL_LIMIT = 5
DEFAULT_TIMEOUT = 30


async def search_products(
    query: str,
    db: Session,
    site_ids: list[int] | None = None,
    max_results: int | None = None,
) -> AsyncGenerator[SearchProgress, None]:
    """
    Recherche des produits sur les sites configurés.

    Flux:
    1. SearXNG recherche les URLs
    2. Light scraper tente extraction HTTP rapide
    3. Browserless fallback pour les sites JS

    Args:
        query: Terme de recherche
        db: Session de base de données
        site_ids: IDs des sites à utiliser (None = tous les actifs)
        max_results: Nombre max de résultats

    Yields:
        SearchProgress avec les résultats au fur et à mesure
    """
    # Récupérer la configuration
    if max_results is None:
        max_results = int(SettingsService.get_setting_value(db, "search_max_results", str(DEFAULT_MAX_RESULTS)))

    parallel_limit = int(SettingsService.get_setting_value(db, "search_parallel_limit", str(DEFAULT_PARALLEL_LIMIT)))

    # Récupérer les sites
    sites = _get_sites(db, site_ids)
    if not sites:
        yield SearchProgress(
            status="error",
            total=0,
            completed=0,
            message="Aucun site de recherche configuré",
            results=[],
        )
        return

    domains = [site.domain for site in sites]
    site_map = {site.domain: site for site in sites}

    # Phase 1: Recherche SearXNG
    yield SearchProgress(
        status="searching",
        total=0,
        completed=0,
        message=f"Recherche sur {len(domains)} sites...",
        results=[],
    )

    searxng_results = await searxng_service.search(
        query=query,
        domains=domains,
        max_results=max_results,
    )

    if not searxng_results:
        yield SearchProgress(
            status="error",
            total=0,
            completed=0,
            message="Aucun résultat trouvé",
            results=[],
        )
        return

    total = len(searxng_results)
    logger.info(f"SearXNG: {total} URLs trouvées pour '{query}'")

    # Phase 2: Scraping des URLs
    results: list[SearchResultItem] = []
    completed = 0

    # Créer un sémaphore pour limiter la concurrence
    semaphore = asyncio.Semaphore(parallel_limit)

    async def process_url(searxng_result: searxng_service.SearXNGResult) -> SearchResultItem | None:
        async with semaphore:
            url = searxng_result.url
            domain = searxng_result.source
            site = site_map.get(domain)

            if not site:
                # Trouver le site par correspondance partielle
                for d, s in site_map.items():
                    if d in domain or domain in d:
                        site = s
                        break

            site_name = site.name if site else domain
            requires_js = site.requires_js if site else False

            # Essayer le scraping léger d'abord (sauf si le site requiert JS)
            if not requires_js:
                light_result = await light_scraper_service.scrape_url(url)

                if light_result.success and light_result.price is not None:
                    return SearchResultItem(
                        url=url,
                        title=light_result.title or searxng_result.title,
                        price=light_result.price,
                        currency=light_result.currency,
                        in_stock=light_result.in_stock,
                        image_url=light_result.image_url,
                        site_name=site_name,
                        site_domain=domain,
                        confidence=0.7,  # Confiance moyenne pour le scraping léger
                    )

            # Fallback: Browserless + IA
            try:
                result = await _scrape_with_browserless(url, site_name, domain, searxng_result.title)
                return result
            except Exception as e:
                logger.error(f"Erreur scraping {url}: {e}")
                return SearchResultItem(
                    url=url,
                    title=searxng_result.title,
                    price=None,
                    site_name=site_name,
                    site_domain=domain,
                    error=str(e),
                )

    # Traiter les URLs en parallèle avec mises à jour progressives
    tasks = [asyncio.create_task(process_url(r)) for r in searxng_results]

    for coro in asyncio.as_completed(tasks):
        try:
            result = await coro
            completed += 1

            if result:
                # N'ajouter que les résultats avec un prix
                if result.price is not None:
                    results.append(result)

                yield SearchProgress(
                    status="scraping",
                    total=total,
                    completed=completed,
                    current_site=result.site_name if result else None,
                    results=results.copy(),
                    message=f"Extraction {completed}/{total}...",
                )
        except Exception as e:
            completed += 1
            logger.error(f"Erreur lors du traitement: {e}")

    # Trier les résultats par prix
    results.sort(key=lambda x: x.price if x.price else float("inf"))

    yield SearchProgress(
        status="completed",
        total=total,
        completed=completed,
        results=results,
        message=f"{len(results)} produits trouvés avec prix",
    )


async def _scrape_with_browserless(
    url: str,
    site_name: str,
    domain: str,
    fallback_title: str,
) -> SearchResultItem:
    """Scrape une URL avec Browserless + extraction IA"""
    try:
        # Scraper avec Browserless
        screenshot_path, page_text = await ScraperService.scrape_item(
            url=url,
            item_id=None,
            smart_scroll=True,
            scroll_pixels=350,
            text_length=3000,
            timeout=30000,
        )

        if not screenshot_path:
            return SearchResultItem(
                url=url,
                title=fallback_title,
                price=None,
                site_name=site_name,
                site_domain=domain,
                error="Screenshot failed",
            )

        # Extraction IA
        ai_result = await ai_service.analyze_image(
            screenshot_path=screenshot_path,
            webpage_text=page_text,
        )

        if ai_result and ai_result.get("price"):
            return SearchResultItem(
                url=url,
                title=fallback_title,
                price=ai_result.get("price"),
                currency=ai_result.get("currency", "EUR"),
                in_stock=ai_result.get("in_stock"),
                image_url=None,  # Pas d'image depuis le screenshot
                site_name=site_name,
                site_domain=domain,
                confidence=ai_result.get("price_confidence", 0.5),
            )

        return SearchResultItem(
            url=url,
            title=fallback_title,
            price=None,
            site_name=site_name,
            site_domain=domain,
            error="AI extraction failed",
        )

    except Exception as e:
        logger.error(f"Browserless scraping error for {url}: {e}")
        return SearchResultItem(
            url=url,
            title=fallback_title,
            price=None,
            site_name=site_name,
            site_domain=domain,
            error=str(e),
        )


def _get_sites(db: Session, site_ids: list[int] | None = None) -> list[SearchSite]:
    """Récupère les sites de recherche actifs"""
    query = db.query(SearchSite).filter(SearchSite.is_active == True)

    if site_ids:
        query = query.filter(SearchSite.id.in_(site_ids))

    return query.order_by(SearchSite.priority).all()


def get_all_sites(db: Session) -> list[SearchSite]:
    """Récupère tous les sites de recherche"""
    return db.query(SearchSite).order_by(SearchSite.priority).all()


def get_site_by_id(db: Session, site_id: int) -> SearchSite | None:
    """Récupère un site par son ID"""
    return db.query(SearchSite).filter(SearchSite.id == site_id).first()


def create_site(db: Session, site_data: dict[str, Any]) -> SearchSite:
    """Crée un nouveau site de recherche"""
    site = SearchSite(**site_data)
    db.add(site)
    db.commit()
    db.refresh(site)
    return site


def update_site(db: Session, site_id: int, site_data: dict[str, Any]) -> SearchSite | None:
    """Met à jour un site de recherche"""
    site = get_site_by_id(db, site_id)
    if not site:
        return None

    for key, value in site_data.items():
        if value is not None:
            setattr(site, key, value)

    db.commit()
    db.refresh(site)
    return site


def delete_site(db: Session, site_id: int) -> bool:
    """Supprime un site de recherche"""
    site = get_site_by_id(db, site_id)
    if not site:
        return False

    db.delete(site)
    db.commit()
    return True
