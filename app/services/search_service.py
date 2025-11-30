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
            # Determine if proxy is needed based on source config
            config = SITE_CONFIGS.get(result.source) if result.source in SITE_CONFIGS else None
            # Fallback: check if source name matches a config key
            if not config:
                for key, cfg in SITE_CONFIGS.items():
                    if cfg["name"] == result.source:
                        config = cfg
                        break
            
            use_proxy = config.get("requires_proxy", False) if config else False

            # Use browserless to get content and screenshot
            # extract_text=True to get visible text for AI analysis
            page_text, screenshot_path = await browserless_service.get_page_content(
                result.url,
                use_proxy=use_proxy,
                wait_selector=None,
                extract_text=True  # Get visible text for AI price extraction
            )

            if not screenshot_path:
                return result

            # Use AI to analyze
            from app.services.ai_service import AIService
            ai_result = await AIService.analyze_image(screenshot_path, page_text=page_text)
            
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
        initial_results = NewSearchService._parse_results(html_content, site_key, search_url, query)
        
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
    def _parse_results(html: str, site_key: str, base_url: str, query: str) -> list[SearchResult]:
        """Parse HTML content to extract search results"""
        config = SITE_CONFIGS[site_key]
        soup = BeautifulSoup(html, "html.parser")
        results = []

        # Prepare query words for filtering
        # Split by whitespace, lowercase, remove special chars if needed, filter out short words
        query_words = [w.lower() for w in query.split() if len(w) > 2]

        # Select product links
        links = soup.select(config["product_selector"])
        
        # Deduplicate links
        seen_urls = set()
        
        for link in links:
            # Limit removed as per user request
            # if len(results) >= 5:
            #    break

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
            
            # If no text, check title attribute or nested image alt
            if not title:
                if link.get("title"):
                    title = link.get("title")
                else:
                    img = link.find("img")
                    if img and img.get("alt"):
                        title = img.get("alt")
            
            # Special case for Stokomani or similar where link might be wrapping text but get_text failed or we selected a container
            if not title and config.get("name") == "Stokomani":
                 # If we selected the container .product-card__title, the link is inside
                 child_link = link.find("a")
                 if child_link:
                     title = child_link.get_text(strip=True)
                     if not href: # Update href if we selected a container
                        href = child_link.get("href")
                        if href:
                            full_url = urljoin(base_url, href)

            if not title or len(title) < 3:
                continue

            # STRICT FILTERING: Check if all query words are in the title
            title_lower = title.lower()
            if query_words:
                all_words_found = True
                for word in query_words:
                    if word not in title_lower:
                        all_words_found = False
                        break
                
                if not all_words_found:
                    # logger.debug(f"Skipping result '{title}' - does not contain all query words: {query_words}")
                    continue

            # Extract Image URL (Enhanced)
            image_url = None
            if "product_image_selector" in config:
                # Search in the link itself first
                img_el = link.select_one(config["product_image_selector"])
                
                # If not found in link, search in parent container
                if not img_el:
                    container = link.find_parent("article") or link.find_parent("div", class_=lambda x: x and "product" in x)
                    if container:
                        img_el = container.select_one(config["product_image_selector"])
                
                if img_el:
                    # Try multiple image attributes in order of priority
                    image_url = (
                        img_el.get("src") or 
                        img_el.get("data-src") or 
                        img_el.get("data-lazy-src") or
                        img_el.get("data-original")
                    )
                    
                    # Handle srcset (use first URL)
                    if not image_url and img_el.get("srcset"):
                        srcset = img_el.get("srcset")
                        image_url = srcset.split(",")[0].split()[0]
            
            # Fallback: Find any img in the link
            if not image_url:
                img = link.find("img")
                if img:
                    image_url = (
                        img.get("src") or 
                        img.get("data-src") or 
                        img.get("data-lazy-src") or
                        img.get("data-original")
                    )
                    
                    # Handle srcset
                    if not image_url and img.get("srcset"):
                        srcset = img.get("srcset")
                        image_url = srcset.split(",")[0].split()[0]

            # Make absolute URL
            if image_url and not image_url.startswith("http"):
                image_url = urljoin(base_url, image_url)


            # Create result
            results.append(SearchResult(
                url=full_url,
                title=title,
                snippet=f"Product from {config['name']}",
                source=config["name"],
                image_url=image_url
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
        initial_results = NewSearchService._parse_results(html_content, site_key, search_url, query)
        
        # Phase 2: Scrape details for each result (Parallel)
        # We want to yield results as they complete, not wait for all
        # Reduced from 3 to 2 to avoid saturating Browserless
        semaphore = asyncio.Semaphore(2) # Limit concurrency per site

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
    """Initialise ou met à jour la base de données avec les sites configurés"""
    updated_count = 0
    created_count = 0
    
    # Get all existing sites mapped by domain
    existing_sites = {
        site.domain.lower().replace("www.", ""): site 
        for site in db.query(SearchSite).all()
    }

    for domain, config in SITE_CONFIGS.items():
        clean_domain = domain.lower().replace("www.", "")
        
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

        if clean_domain in existing_sites:
            # Update existing site
            site = existing_sites[clean_domain]
            changed = False
            for key, value in site_data.items():
                if getattr(site, key) != value:
                    setattr(site, key, value)
                    changed = True
            
            if changed:
                try:
                    db.commit()
                    updated_count += 1
                    logger.info(f"Site mis à jour: {domain}")
                except Exception as e:
                    db.rollback()
                    logger.error(f"Erreur mise à jour site {domain}: {e}")
        else:
            # Create new site
            try:
                site = SearchSite(**site_data)
                db.add(site)
                db.commit()
                created_count += 1
                logger.info(f"Nouveau site créé: {domain}")
            except Exception as e:
                db.rollback()
                logger.error(f"Erreur création site {domain}: {e}")

    return created_count + updated_count

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

    # IMPORTANT: Limit concurrent sites to avoid saturating Browserless
    # Max 2 sites can search in parallel, others wait
    site_semaphore = asyncio.Semaphore(2)

    async def producer(gen):
        async with site_semaphore:  # Wait for slot before starting search
            try:
                async for item in gen:
                    await queue.put(item)
            except Exception as e:
                logger.error(f"Error in search producer: {e}")
            finally:
                await queue.put(None) # Sentinel

    # Start producers (limited by semaphore)
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
