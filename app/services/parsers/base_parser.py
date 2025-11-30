"""
Base Parser - Abstract interface for site-specific parsers
Defines the common structure all parsers must implement
"""

import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from urllib.parse import urljoin

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


@dataclass
class ProductResult:
    """Unified product result data structure"""
    title: str
    url: str
    source: str
    price: float | None = None
    original_price: float | None = None
    currency: str = "EUR"
    in_stock: bool | None = None
    image_url: str | None = None
    rating: float | None = None
    reviews_count: int | None = None
    sponsored: bool = False
    snippet: str = ""


class BaseParser(ABC):
    """
    Abstract base class for site-specific parsers

    Each parser must implement:
    - parse_search_results: Extract products from search page HTML
    - parse_product_details: Extract details from product page HTML (optional)
    """

    def __init__(self, site_name: str, base_url: str):
        self.site_name = site_name
        self.base_url = base_url
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    @abstractmethod
    def parse_search_results(self, html: str, query: str, search_url: str) -> list[ProductResult]:
        """
        Parse search results page HTML to extract products

        Args:
            html: Raw HTML content of search page
            query: Original search query
            search_url: URL of the search page

        Returns:
            List of ProductResult objects
        """
        pass

    def parse_product_details(self, html: str, product_url: str) -> dict:
        """
        Parse product detail page to extract price, stock, etc.

        Optional: Override this if you need to scrape individual product pages

        Args:
            html: Raw HTML of product page
            product_url: URL of the product

        Returns:
            Dict with price, in_stock, etc.
        """
        return {}

    # ==================== HELPER METHODS ====================

    def make_absolute_url(self, url: str, base_url: str | None = None) -> str:
        """Convert relative URL to absolute URL"""
        if not url:
            return ""
        if url.startswith("http"):
            return url
        return urljoin(base_url or self.base_url, url)

    def parse_price_text(self, price_text: str) -> float | None:
        """
        Parse French price format to float

        Handles:
        - "12,99 €"
        - "12,99€"
        - "1 234,99 €"
        - "12.99 EUR"
        """
        if not price_text:
            return None

        # Remove currency symbols
        cleaned = price_text.strip().replace('€', '').replace('EUR', '').strip()

        # Remove thousands separators
        cleaned = cleaned.replace(' ', '').replace('\xa0', '')

        # Replace French decimal separator
        cleaned = cleaned.replace(',', '.')

        # Extract first number
        match = re.search(r'(\d+\.?\d*)', cleaned)
        if match:
            try:
                price = float(match.group(1))
                # Validate range
                if 0.01 <= price <= 100000:
                    return price
            except ValueError:
                pass

        return None

    def parse_rating_text(self, rating_text: str) -> float | None:
        """Parse rating like '4,5 sur 5 étoiles'"""
        if not rating_text:
            return None

        match = re.search(r'(\d+[,.]\d+)', rating_text)
        if match:
            try:
                return float(match.group(1).replace(',', '.'))
            except ValueError:
                pass

        return None

    def parse_reviews_count_text(self, reviews_text: str) -> int | None:
        """Parse review count like '1 234'"""
        if not reviews_text:
            return None

        cleaned = re.sub(r'[^\d\s]', '', reviews_text)
        cleaned = cleaned.replace(' ', '').replace('\xa0', '')

        try:
            return int(cleaned)
        except ValueError:
            return None

    def filter_by_query(self, title: str, query: str, strict: bool = False) -> bool:
        """
        Check if title matches query words

        Args:
            title: Product title
            query: Search query
            strict: If True, ALL query words must be in title. If False, at least ONE word.
        """
        if not query:
            return True

        title_lower = title.lower()
        query_words = [w.lower() for w in query.split() if len(w) > 2]

        if not query_words:
            return True

        if strict:
            # All words must be present
            return all(word in title_lower for word in query_words)
        else:
            # At least one word must be present
            return any(word in title_lower for word in query_words)

    def extract_image_url(self, element, selectors: list[str] = None) -> str | None:
        """
        Extract image URL from element with fallback selectors

        Args:
            element: BeautifulSoup element
            selectors: Optional CSS selectors to try
        """
        if selectors:
            for selector in selectors:
                img = element.select_one(selector)
                if img:
                    url = self._get_image_src(img)
                    if url:
                        return url

        # Fallback: find any img
        img = element.find("img")
        if img:
            return self._get_image_src(img)

        # Try picture element
        picture = element.find("picture")
        if picture:
            source = picture.find("source")
            if source and source.get("srcset"):
                return source.get("srcset").split(",")[0].split()[0]
            img = picture.find("img")
            if img:
                return self._get_image_src(img)

        return None

    def _get_image_src(self, img_element) -> str | None:
        """Extract image source from img element"""
        attrs = ['src', 'data-src', 'data-lazy-src', 'data-original', 'data-lazy']

        for attr in attrs:
            url = img_element.get(attr)
            if url and not url.startswith('data:'):
                return url

        # Try srcset
        srcset = img_element.get('srcset')
        if srcset:
            return srcset.split(",")[0].split()[0]

        return None
