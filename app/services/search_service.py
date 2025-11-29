"""
Search Service
Orchestrates searches across multiple e-commerce sites using BrowserlessService.
Includes compatibility methods for API routers.
"""

import asyncio
import logging
import re
from typing import Any, AsyncGenerator
from urllib.parse import quote_plus, urljoin

from bs4 import BeautifulSoup
from sqlalchemy.orm import Session

from app.core.search_config import SITE_CONFIGS
from app.models import SearchSite
from app.schemas import SearchProgress, SearchResultItem
from app.services.browserless_service import browserless_service

logger = logging.getLogger(__name__)

class SearchResult:
    def __init__(
        self,
        url: str,
        title: str,
        snippet: str,
        source: str,
        price: float | None = None,
        currency: str = "EUR",
        in_stock: bool | None = None,
        image_url: str | None = None,
    ):
        self.url = url
        self.title = title
        self.snippet = snippet
        self.source = source
        self.price = price
        self.currency = currency
        self.in_stock = in_stock
        self.image_url = image_url

    def to_dict(self):
        return {
            "url": self.url,
            "title": self.title,
            "snippet": self.snippet,
            "source": self.source,
            "price": self.price,
            "currency": self.currency,
            "in_stock": self.in_stock,
            "image_url": self.image_url,
        }

class NewSearchService:
    @staticmethod
    async def search_site(site_key: str, query: str) -> list[SearchResult]:
        """Search a single site"""
        config = SITE_CONFIGS.get(site_key)
        if not config:
            logger.error(f"Unknown site: {site_key}")
            return []

        search_url = config["search_url"].format(query=quote_plus(query))
        logger.info(f"Searching {config['name']} at {search_url}")

        # Use proxy if required by config
        use_proxy = config.get("requires_proxy", False)
        
        html_content, _ = await browserless_service.get_page_content(
            search_url, 
            use_proxy=use_proxy,
            wait_selector=config.get("wait_selector")
        )

        if not html_content:
            logger.warning(f"No content returned for {site_key}")
            return []

        return NewSearchService._parse_results(html_content, site_key, search_url)

    @staticmethod
    async def scrape_item(result: SearchResult) -> SearchResult:
        """Scrape details for a single item"""
        try:
            # Use browserless to get content and screenshot
            html, screenshot_path = await browserless_service.get_page_content(
                result.url,
                use_proxy="amazon" in result.source.lower(),
                wait_selector=None 
            )
            
            if not screenshot_path:
                return result

            # Use AI to analyze
            from app.services.ai_service import AIService
            ai_result = await AIService.analyze_image(screenshot_path, page_text=html)
            
            if ai_result:
                extraction, _ = ai_result
                result.price = extraction.price
                result.currency = extraction.currency or "EUR"
                result.in_stock = extraction.in_stock
                
                # Update image URL to point to our local screenshot
                # The frontend expects /screenshots/filename
                import os
                filename = os.path.basename(screenshot_path)
                result.image_url = f"/screenshots/{filename}"
                
        except Exception as e:
            logger.error(f"Error scraping item {result.url}: {e}")
            
        return result

    @staticmethod
    async def search_site(site_key: str, query: str) -> list[SearchResult]:
        """Search a single site"""
        config = SITE_CONFIGS.get(site_key)
        if not config:
            logger.error(f"Unknown site: {site_key}")
            return []

        search_url = config["search_url"].format(query=quote_plus(query))
        logger.info(f"Searching {config['name']} at {search_url}")

        # Use proxy if required by config
        use_proxy = config.get("requires_proxy", False)
        
        html_content, _ = await browserless_service.get_page_content(
            search_url, 
            use_proxy=use_proxy,
            wait_selector=config.get("wait_selector")
        )

        if not html_content:
            logger.warning(f"No content returned for {site_key}")
            return []

        # Phase 1: Parse results
        initial_results = NewSearchService._parse_results(html_content, site_key, search_url)
        
        # Phase 2: Scrape details for each result (Parallel)
        # Limit concurrency to avoid overloading
        semaphore = asyncio.Semaphore(3)
        
        async def scrape_with_limit(res):
            async with semaphore:
                return await NewSearchService.scrape_item(res)

        tasks = [scrape_with_limit(r) for r in initial_results]
        enriched_results = await asyncio.gather(*tasks)
        
        return enriched_results

    @staticmethod
    def _parse_results(html: str, site_key: str, base_url: str) -> list[SearchResult]:
        """Parse HTML content to extract search results"""
        config = SITE_CONFIGS[site_key]
        soup = BeautifulSoup(html, "html.parser")
        results = []

        # Select product links
        links = soup.select(config["product_selector"])
        
        # Deduplicate links
        seen_urls = set()
        
        for link in links:
            if len(results) >= 5:  # Limit to 5 results per site
                break

            href = link.get("href")
            if not href:
                continue

            full_url = urljoin(base_url, href)
            
            # Basic cleanup
            if full_url in seen_urls:
                continue
            seen_urls.add(full_url)

            # Extract title
            title = link.get_text(strip=True)
            if not title:
                # Try finding title in children or attributes
                img = link.find("img")
                if img and img.get("alt"):
                    title = img.get("alt")
                elif link.get("title"):
                    title = link.get("title")
            
            if not title or len(title) < 3:
                continue

            # Create result
            results.append(SearchResult(
                url=full_url,
                title=title,
                snippet=f"Product from {config['name']}",
                source=config["name"]
            ))

        logger.info(f"Found {len(results)} results for {site_key}")
        return results

    @staticmethod
    async def search_site_generator(site_key: str, query: str) -> AsyncGenerator[SearchResult, None]:
        """Search a single site and yield results as they are scraped"""
        config = SITE_CONFIGS.get(site_key)
        if not config:
            logger.error(f"Unknown site: {site_key}")
            return

        search_url = config["search_url"].format(query=quote_plus(query))
        logger.info(f"Searching {config['name']} at {search_url}")

        # Use proxy if required by config
        use_proxy = config.get("requires_proxy", False)
        
        html_content, _ = await browserless_service.get_page_content(
            search_url, 
            use_proxy=use_proxy,
            wait_selector=config.get("wait_selector")
        )

        if not html_content:
            logger.warning(f"No content returned for {site_key}")
            return

        # Phase 1: Parse results
        initial_results = NewSearchService._parse_results(html_content, site_key, search_url)
        
        # Phase 2: Scrape details for each result (Parallel)
        # We want to yield results as they complete, not wait for all
        semaphore = asyncio.Semaphore(3) # Limit concurrency per site

        async def scrape_wrapper(res):
            async with semaphore:
                return await NewSearchService.scrape_item(res)

        tasks = [scrape_wrapper(r) for r in initial_results]
        
        for future in asyncio.as_completed(tasks):
            enriched_res = await future
            yield enriched_res

    @staticmethod
    async def search_all(query: str) -> list[SearchResult]:
        """Legacy method for compatibility"""
        results = []
        # This is not optimized for streaming, but keeps old signature
        tasks = []
        for site_key in SITE_CONFIGS.keys():
            tasks.append(NewSearchService.search_site(site_key, query))
        
        results_list = await asyncio.gather(*tasks)
        for r in results_list:
            results.extend(r)
        return results

# Global instance
new_search_service = NewSearchService()

# ==========================================
# COMPATIBILITY LAYER FOR API ROUTERS
# ==========================================

def get_all_sites(db: Session) -> list[SearchSite]:
    """Récupère tous les sites de recherche"""
    return db.query(SearchSite).order_by(SearchSite.priority).all()

def get_site_by_id(db: Session, site_id: int) -> SearchSite | None:
    """Récupère un site par son ID"""
    return db.query(SearchSite).filter(SearchSite.id == site_id).first()

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

def seed_default_sites(db: Session) -> int:
    """Initialise la base de données avec les sites configurés"""
    created_count = 0
    existing_domains = {site.domain.lower().replace("www.", "") for site in db.query(SearchSite).all()}

    for domain, config in SITE_CONFIGS.items():
        clean_domain = domain.lower().replace("www.", "")
        if clean_domain in existing_domains:
            continue

        site_data = {
            "name": config.get("name", domain),
            "domain": domain,
            "search_url": config.get("search_url"),
            "product_link_selector": config.get("product_selector"),
            "category": config.get("category"),
            "requires_js": True, # Always true for browserless
            "priority": 99,
            "is_active": True,
        }

        try:
            site = SearchSite(**site_data)
            db.add(site)
            db.commit()
            created_count += 1
        except Exception as e:
            db.rollback()
            logger.error(f"Erreur création site {domain}: {e}")

    return created_count

def reset_sites_to_defaults(db: Session) -> int:
    """Réinitialise tous les sites"""
    db.query(SearchSite).delete()
    db.commit()
    return seed_default_sites(db)

async def search_products(
    query: str,
    db: Session,
    site_ids: list[int] | None = None,
    max_results: int | None = None,
) -> AsyncGenerator[SearchProgress, None]:
    """
    Compatibility wrapper for search_products.
    Yields SearchProgress events incrementally.
    """
    # 1. Get sites to search
    sites = get_all_sites(db)
    if site_ids:
        sites = [s for s in sites if s.id in site_ids]
    
    active_sites = [s for s in sites if s.is_active]
    
    # Initial event
    yield SearchProgress(
        status="searching",
        total=len(active_sites),
        completed=0,
        message=f"Démarrage de la recherche sur {len(active_sites)} sites...",
        results=[],
    )

    # 2. Map DB sites to Config keys
    site_keys = []
    for site in active_sites:
        for key in SITE_CONFIGS.keys():
            if key in site.domain or site.domain in key:
                site_keys.append(key)
                break
    
    # 3. Execute searches and stream results
    # We create a task for each site generator
    
    generators = [NewSearchService.search_site_generator(key, query) for key in site_keys]
    
    # We need to iterate over multiple async generators concurrently
    # This is a bit complex, so we'll use a queue or similar
    # Simpler approach: Use aiostream if available, or just interleave manually
    # For now, let's just run them and yield as we get them.
    # Since we want to show results ASAP, we can use asyncio.as_completed on the *next* item of each generator?
    # No, generators are stateful.
    
    # Simplest robust approach without extra libs:
    # Create a wrapper task for each generator that puts items into a shared Queue
    
    queue = asyncio.Queue()
    active_producers = len(generators)
    
    async def producer(gen):
        try:
            async for item in gen:
                await queue.put(item)
        except Exception as e:
            logger.error(f"Error in search producer: {e}")
        finally:
            await queue.put(None) # Sentinel

    # Start producers
    for gen in generators:
        asyncio.create_task(producer(gen))
        
    # Consumer loop
    results_so_far = []
    completed_sites = 0
    
    while active_producers > 0:
        item = await queue.get()
        
        if item is None:
            active_producers -= 1
            completed_sites += 1
            # Optional: yield progress update without new result
            yield SearchProgress(
                status="searching",
                total=len(active_sites),
                completed=completed_sites,
                message=f"Recherche en cours... ({completed_sites}/{len(active_sites)} sites terminés)",
                results=results_so_far,
            )
        else:
            # Convert to SearchResultItem
            api_item = SearchResultItem(
                url=item.url,
                title=item.title,
                price=item.price,
                currency=item.currency,
                in_stock=item.in_stock,
                site_name=item.source,
                site_domain=item.source,
                image_url=item.image_url,
            )
            results_so_far.append(api_item)
            
            # Yield update with new result
            yield SearchProgress(
                status="searching",
                total=len(active_sites),
                completed=completed_sites,
                message=f"Trouvé: {item.title[:30]}...",
                results=results_so_far,
            )
            
    # Final event
    yield SearchProgress(
        status="completed",
        total=len(active_sites),
        completed=len(active_sites),
        message=f"Terminé. {len(results_so_far)} résultats trouvés.",
        results=results_so_far,
    )
