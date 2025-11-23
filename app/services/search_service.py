"""
Search Service - Orchestrateur de recherche de produits
Combine recherche directe sur sites + Light Scraper + Browserless fallback
"""

import asyncio
import logging
import os
from collections.abc import AsyncGenerator
from typing import Any

from playwright.async_api import async_playwright
from sqlalchemy.orm import Session

from app.models import SearchSite
from app.schemas import SearchProgress, SearchResultItem
from app.services import direct_search_service, light_scraper_service
from app.services.ai_service import AIService
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
    1. Recherche directe sur les pages de recherche de chaque site
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

    # Préparer les données des sites pour la recherche directe
    sites_data = [
        {
            "domain": site.domain,
            "name": site.name,
            "search_url": site.search_url,
            "product_link_selector": site.product_link_selector,
            "requires_js": site.requires_js,
        }
        for site in sites
    ]
    site_map = {site.domain: site for site in sites}

    # Phase 1: Recherche directe sur les sites
    yield SearchProgress(
        status="searching",
        total=0,
        completed=0,
        message=f"Recherche sur {len(sites)} sites...",
        results=[],
    )

    browser = None
    playwright = None
    
    try:
        # Initialiser Playwright et Browserless pour TOUTE la session de recherche
        logger.info(f"Initialisation session Browserless globale pour '{query}'")
        playwright = await async_playwright().start()
        browser = await playwright.chromium.connect_over_cdp(
            os.getenv("BROWSERLESS_URL", "ws://browserless:3000"),
            timeout=60000
        )

        try:
            search_results = await direct_search_service.search(
                query=query,
                sites=sites_data,
                max_results=max_results,
                browser=browser,  # Utiliser le navigateur partagé
            )
        except Exception as e:
            logger.error(f"Erreur critique lors de la recherche directe: {e}")
            yield SearchProgress(
                status="error",
                total=0,
                completed=0,
                message=f"Erreur de recherche: {str(e)}",
                results=[],
            )
            return

        if not search_results:
            yield SearchProgress(
                status="completed",
                total=0,
                completed=0,
                message="Aucun résultat trouvé sur les sites configurés",
                results=[],
            )
            return

        total = len(search_results)
        logger.info(f"Recherche directe: {total} URLs trouvées pour '{query}'")

        # Phase 2: Scraping des URLs
        results: list[SearchResultItem] = []
        completed = 0

        # Créer un sémaphore pour limiter la concurrence
        semaphore = asyncio.Semaphore(parallel_limit)

        async def process_url(search_result: direct_search_service.SearchResult) -> SearchResultItem | None:
            async with semaphore:
                url = search_result.url
                domain = search_result.source
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
                            title=light_result.title or search_result.title,
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
                    # Passer le navigateur partagé
                    result = await _scrape_with_browserless(url, site_name, domain, search_result.title, browser)
                    return result
                except Exception as e:
                    logger.error(f"Erreur scraping {url}: {e}")
                    return SearchResultItem(
                        url=url,
                        title=search_result.title,
                        price=None,
                        site_name=site_name,
                        site_domain=domain,
                        error=str(e),
                    )

        # Traiter les URLs en parallèle avec mises à jour progressives
        tasks = [asyncio.create_task(process_url(r)) for r in search_results]

        for coro in asyncio.as_completed(tasks):
            try:
                result = await coro
                completed += 1

                if result:
                    # Ajouter tous les résultats, même sans prix (le frontend affichera "Prix non disponible")
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
        
    finally:
        # Nettoyage global des ressources
        if browser:
            try:
                if browser.is_connected():
                    await browser.close()
                logger.info("Navigateur global fermé")
            except Exception as e:
                logger.error(f"Erreur fermeture navigateur: {e}")
        
        # Petit délai pour laisser le temps aux connexions de se fermer proprement
        await asyncio.sleep(0.5)
                
        if playwright:
            try:
                await playwright.stop()
            except Exception as e:
                # Ignorer les erreurs courantes lors de l'arrêt si déjà fermé
                if "Event loop is closed" not in str(e):
                    logger.error(f"Erreur arrêt Playwright: {e}")


async def _scrape_with_browserless(
    url: str,
    site_name: str,
    domain: str,
    fallback_title: str,
    browser=None,  # Navigateur partagé
) -> SearchResultItem:
    """Scrape une URL avec Browserless + extraction IA"""
    try:
        # Scraper avec Browserless (utiliser le navigateur partagé)
        screenshot_path, page_text, is_available = await ScraperService.scrape_item(
            url=url,
            item_id=None,
            smart_scroll=True,
            scroll_pixels=350,
            text_length=3000,
            timeout=30000,
            browser=browser,
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
        ai_result = await AIService.analyze_image(
            image_path=screenshot_path,
            page_text=page_text,
        )

        # Construire l'URL du screenshot pour le frontend
        screenshot_url = None
        if screenshot_path:
            screenshot_filename = os.path.basename(screenshot_path)
            screenshot_url = f"/screenshots/{screenshot_filename}"

        if ai_result:
            extraction, metadata = ai_result
            if extraction and extraction.price is not None:
                return SearchResultItem(
                    url=url,
                    title=fallback_title,
                    price=extraction.price,
                    currency=extraction.currency or "EUR",
                    in_stock=extraction.in_stock,
                    image_url=screenshot_url,
                    site_name=site_name,
                    site_domain=domain,
                    confidence=extraction.price_confidence or 0.5,
                )

        return SearchResultItem(
            url=url,
            title=fallback_title,
            price=None,
            image_url=screenshot_url,
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


def seed_default_sites(db: Session) -> int:
    """
    Initialise la base de données avec les sites configurés en dur.
    Ne crée que les sites qui n'existent pas encore (basé sur le domaine).

    Returns:
        Nombre de sites créés
    """
    from app.services.direct_search_service import DEFAULT_SITE_CONFIGS

    created_count = 0

    # Récupérer les domaines existants
    existing_domains = {site.domain.lower().replace("www.", "")
                       for site in db.query(SearchSite).all()}

    for domain, config in DEFAULT_SITE_CONFIGS.items():
        # Normaliser le domaine pour comparaison
        clean_domain = domain.lower().replace("www.", "")

        # Ne pas créer si déjà existant
        if clean_domain in existing_domains:
            logger.debug(f"Site {domain} déjà existant, ignoré")
            continue

        # Créer le site
        site_data = {
            "name": config.get("name", domain),
            "domain": domain,
            "search_url": config.get("search_url"),
            "product_link_selector": config.get("product_selector"),
            "category": config.get("category"),
            "requires_js": config.get("requires_js", True),
            "priority": config.get("priority", 99),
            "is_active": True,
        }

        try:
            site = SearchSite(**site_data)
            db.add(site)
            db.commit()
            created_count += 1
            logger.info(f"Site créé: {config.get('name', domain)} ({domain})")
        except Exception as e:
            db.rollback()
            logger.error(f"Erreur création site {domain}: {e}")

    return created_count


def reset_sites_to_defaults(db: Session) -> int:
    """
    Réinitialise tous les sites avec les valeurs par défaut.
    Supprime tous les sites existants et recrée à partir de la config.

    Returns:
        Nombre de sites créés
    """
    from app.services.direct_search_service import DEFAULT_SITE_CONFIGS

    # Supprimer tous les sites existants
    db.query(SearchSite).delete()
    db.commit()
    logger.info("Tous les sites supprimés")

    # Recréer avec les valeurs par défaut
    created_count = 0

    for domain, config in DEFAULT_SITE_CONFIGS.items():
        site_data = {
            "name": config.get("name", domain),
            "domain": domain,
            "search_url": config.get("search_url"),
            "product_link_selector": config.get("product_selector"),
            "category": config.get("category"),
            "requires_js": config.get("requires_js", True),
            "priority": config.get("priority", 99),
            "is_active": True,
        }

        try:
            site = SearchSite(**site_data)
            db.add(site)
            db.commit()
            created_count += 1
            logger.info(f"Site créé: {config.get('name', domain)} ({domain})")
        except Exception as e:
            db.rollback()
            logger.error(f"Erreur création site {domain}: {e}")

    return created_count
