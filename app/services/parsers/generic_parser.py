"""
Generic Parser - Fallback parser for sites without specific implementation
Uses configuration from search_config.py
"""

from bs4 import BeautifulSoup
from urllib.parse import urljoin

from .base_parser import BaseParser, ProductResult
from app.core.search_config import SITE_CONFIGS


class GenericParser(BaseParser):
    """
    Generic parser using configured selectors from search_config.py

    This parser is used as a fallback for sites that don't have
    a specialized parser implementation.
    """

    def __init__(self, site_key: str):
        """
        Initialize with site configuration

        Args:
            site_key: Key in SITE_CONFIGS dict
        """
        config = SITE_CONFIGS.get(site_key)
        if not config:
            raise ValueError(f"Unknown site key: {site_key}")

        super().__init__(
            site_name=config.get("name", site_key),
            base_url=config.get("search_url", "").split("/")[0:3]  # Extract base URL
        )

        self.config = config
        self.site_key = site_key

        # Extract base_url properly
        if "search_url" in config:
            parts = config["search_url"].split("/")
            if len(parts) >= 3:
                self.base_url = f"{parts[0]}//{parts[2]}"

    def parse_search_results(self, html: str, query: str, search_url: str) -> list[ProductResult]:
        """
        Parse search results using configured selectors

        Uses:
        - product_selector: CSS selector for product links
        - product_image_selector: CSS selector for images (optional)

        If configured selector fails, tries common fallback selectors.
        """
        soup = BeautifulSoup(html, 'html.parser')
        products = []

        # Get product links using configured selector
        product_selector = self.config.get("product_selector")
        if not product_selector:
            self.logger.error(f"No product_selector configured for {self.site_key}")
            return []

        links = soup.select(product_selector)

        # If configured selector fails, try common fallback selectors
        if not links:
            self.logger.warning(f"No products with configured selector: {product_selector}")
            self.logger.info("Trying fallback selectors...")

            # Common e-commerce selectors (ordered by specificity)
            fallback_selectors = [
                # Product-specific URLs
                "a[href*='/produit']",
                "a[href*='/product']",
                "a[href*='/p/']",
                "a[href*='/item']",
                # Common class patterns
                "article a[href]",
                ".product a[href]",
                ".product-card a[href]",
                ".product-item a[href]",
                "[class*='product'] a[href]",
                # Generic structure
                "article[class*='product'] a",
                "div[class*='product'] a",
                # Very generic (last resort)
                "a[class*='product']",
            ]

            for fallback in fallback_selectors:
                links = soup.select(fallback)
                if links and len(links) >= 3:  # At least 3 links to be credible
                    self.logger.info(f"✓ Found {len(links)} links with fallback: {fallback}")
                    break

        if not links:
            self.logger.warning(f"No products found for {self.site_key} even with fallbacks")
            return []

        self.logger.info(f"Found {len(links)} product links for {self.site_name}")

        seen_urls = set()

        for link in links:
            try:
                href = link.get("href")
                if not href:
                    continue

                full_url = urljoin(search_url, href)

                if full_url in seen_urls:
                    continue
                seen_urls.add(full_url)

                # Extract title
                title = link.get_text(strip=True)

                # Fallback: try title attribute or alt in img
                if not title:
                    title = link.get("title", "")
                if not title:
                    img = link.find("img")
                    if img:
                        title = img.get("alt", "")

                if not title or len(title) < 3:
                    self.logger.debug(f"Skipped: empty or too short title")
                    continue

                self.logger.debug(f"Extracted title: '{title[:60]}'...")

                # RELAXED FILTERING: Only filter out if title is completely unrelated
                # Accept product if:
                # 1. Query is empty/short
                # 2. At least one query word is in title (case-insensitive)
                # 3. Title length is reasonable (not just numbers/symbols)
                if query and len(query) > 2:
                    # Very permissive: keep if ANY query word matches OR title is substantial
                    query_words = [w.lower() for w in query.split() if len(w) > 2]
                    title_lower = title.lower()

                    if query_words:
                        # Check if at least one word matches
                        has_match = any(word in title_lower for word in query_words)

                        # If no match and title is very short, skip
                        # But if title is substantial (>15 chars), keep it anyway (might be relevant)
                        if not has_match and len(title) < 15:
                            self.logger.debug(f"Filtered: '{title[:40]}' - no query match and too short")
                            continue

                # Extract image using configured selector
                image_url = None
                image_selector = self.config.get("product_image_selector")

                if image_selector:
                    # Try in link first
                    img_elem = link.select_one(image_selector)

                    # Try in parent container
                    if not img_elem:
                        parent = link.find_parent(["article", "li", "div"])
                        if parent:
                            img_elem = parent.select_one(image_selector)

                    if img_elem:
                        image_url = self._get_image_src(img_elem)

                # Fallback: any img in link or parent
                if not image_url:
                    img = link.find("img")
                    if img:
                        image_url = self._get_image_src(img)

                    if not image_url:
                        parent = link.find_parent(["article", "li", "div"])
                        if parent:
                            img = parent.find("img")
                            if img:
                                image_url = self._get_image_src(img)

                # Make image URL absolute
                if image_url:
                    # Skip invalid images
                    if image_url.startswith("data:") or "1x1" in image_url or "placeholder" in image_url.lower():
                        image_url = None
                    else:
                        image_url = urljoin(search_url, image_url)

                products.append(ProductResult(
                    title=title,
                    url=full_url,
                    source=self.site_name,
                    image_url=image_url,
                    currency="EUR",
                    snippet=f"Product from {self.site_name}"
                ))

            except Exception as e:
                self.logger.error(f"Error parsing product from {self.site_key}: {e}")
                continue

        self.logger.info(f"Extracted {len(products)} products from {self.site_name}")
        return products
