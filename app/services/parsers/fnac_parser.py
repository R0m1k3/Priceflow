"""
Fnac Parser - Specialized parser for Fnac.com
"""

from bs4 import BeautifulSoup

from .base_parser import BaseParser, ProductResult


class FnacParser(BaseParser):
    """
    Parser for Fnac.com

    Key selectors:
    - Product links: a[href*='/a'], a.Article-title, article a
    - Images: img, picture source
    """

    def __init__(self):
        super().__init__(
            site_name="Fnac",
            base_url="https://www.fnac.com"
        )

    def parse_search_results(self, html: str, query: str, search_url: str) -> list[ProductResult]:
        """Parse Fnac search results"""
        soup = BeautifulSoup(html, 'html.parser')
        products = []

        # Try multiple selectors
        selectors = [
            "a[href*='/a']",
            "a.Article-title",
            "article a",
            ".Article-item a",
        ]

        links = []
        for selector in selectors:
            links = soup.select(selector)
            if links:
                self.logger.info(f"Found {len(links)} products with selector: {selector}")
                break

        if not links:
            self.logger.warning("No products found on Fnac")
            return []

        seen_urls = set()

        for link in links:
            try:
                href = link.get("href")
                if not href:
                    continue

                # Filter Fnac URLs
                if "/a" not in href:
                    continue

                full_url = self.make_absolute_url(href)

                if full_url in seen_urls:
                    continue
                seen_urls.add(full_url)

                # Extract title
                title = link.get_text(strip=True)
                if not title:
                    title = link.get("title", "")

                # Try aria-label
                if not title:
                    title = link.get("aria-label", "")

                if not title or len(title) < 3:
                    continue

                # Filter by query
                if not self.filter_by_query(title, query):
                    continue

                # Extract image
                image_url = None
                parent = link.find_parent(["article", "li", "div"])
                if parent:
                    # Try picture > source first
                    picture = parent.find("picture")
                    if picture:
                        source = picture.find("source")
                        if source and source.get("srcset"):
                            image_url = source.get("srcset").split(",")[0].split()[0]
                        if not image_url:
                            img = picture.find("img")
                            if img:
                                image_url = self._get_image_src(img)

                    # Fallback to img
                    if not image_url:
                        img = parent.find("img")
                        if img:
                            image_url = self._get_image_src(img)

                    if image_url:
                        image_url = self.make_absolute_url(image_url)

                # Extract price
                price = None
                if parent:
                    price_selectors = [
                        ".Article-price",
                        "[class*='price']",
                        "span[class*='prix']",
                        "[data-testid='price']",
                    ]
                    for price_sel in price_selectors:
                        price_elem = parent.select_one(price_sel)
                        if price_elem:
                            price = self.parse_price_text(price_elem.get_text(strip=True))
                            if price:
                                break

                products.append(ProductResult(
                    title=title,
                    url=full_url,
                    source=self.site_name,
                    price=price,
                    currency="EUR",
                    image_url=image_url,
                    snippet=f"Product from {self.site_name}"
                ))

            except Exception as e:
                self.logger.error(f"Error parsing Fnac product: {e}")
                continue

        self.logger.info(f"Extracted {len(products)} products from Fnac")
        return products
