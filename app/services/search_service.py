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
    ):
        self.url = url
        self.title = title
        self.snippet = snippet
        self.source = source
        self.price = price
        self.currency = currency
        self.in_stock = in_stock

    def to_dict(self):
        return {
            "url": self.url,
            "title": self.title,
            "snippet": self.snippet,
            "source": self.source,
            "price": self.price,
            "currency": self.currency,
            "in_stock": self.in_stock,
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
    async def search_all(query: str) -> list[SearchResult]:
        """Search all configured sites in parallel"""
        tasks = []
        for site_key in SITE_CONFIGS.keys():
            tasks.append(NewSearchService.search_site(site_key, query))
        
        results_list = await asyncio.gather(*tasks)
        
        # Flatten list
        all_results = []
        for site_results in results_list:
            all_results.extend(site_results)
            
        return all_results

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
    Yields SearchProgress events.
    """
    # 1. Get sites to search
    sites = get_all_sites(db)
    if site_ids:
        sites = [s for s in sites if s.id in site_ids]
    
    active_sites = [s for s in sites if s.is_active]
    
    yield SearchProgress(
        status="searching",
        total=len(active_sites),
        completed=0,
        message=f"Recherche sur {len(active_sites)} sites...",
        results=[],
    )

    # 2. Map DB sites to Config keys
    # We need to match DB sites (domain) to SITE_CONFIGS keys
    tasks = []
    
    for site in active_sites:
        # Find matching config key
        site_key = None
        for key in SITE_CONFIGS.keys():
            if key in site.domain or site.domain in key:
                site_key = key
                break
        
        if site_key:
            tasks.append(NewSearchService.search_site(site_key, query))
        else:
            logger.warning(f"No config found for site {site.domain}")

    # 3. Execute searches
    # To stream results, we should ideally use as_completed, but search_site returns a list
    # Let's just wait for all for now to keep it simple, or implement a generator in NewSearchService
    
    # Simple implementation: Wait for all (streaming is harder with current architecture)
    results_lists = await asyncio.gather(*tasks)
    
    all_results = []
    for res_list in results_lists:
        for r in res_list:
            all_results.append(SearchResultItem(
                url=r.url,
                title=r.title,
                price=r.price,
                currency=r.currency,
                in_stock=r.in_stock,
                site_name=r.source,
                site_domain=r.source, # approximate
            ))
    
    yield SearchProgress(
        status="completed",
        total=len(active_sites),
        completed=len(active_sites),
        message=f"Terminé. {len(all_results)} résultats trouvés.",
        results=all_results,
    )
