"""
New Search Service
Orchestrates searches across multiple e-commerce sites using BrowserlessService.
"""

import asyncio
import logging
import re
from urllib.parse import quote_plus, urljoin

from bs4 import BeautifulSoup

from app.core.search_config import SITE_CONFIGS
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
