"""
Darty Parser - Specialized parser for Darty.com
"""

from bs4 import BeautifulSoup

from .base_parser import BaseParser, ProductResult


class DartyParser(BaseParser):
    """
    Parser for Darty.com

    Key selectors:
    - Product links: a[href*='/nav/achat/'][href*='.html']
    - Images: img.product_img
    """

    def __init__(self):
        super().__init__(
            site_name="Darty",
            base_url="https://www.darty.com"
        )

    def parse_search_results(self, html: str, query: str, search_url: str) -> list[ProductResult]:
        """Parse Darty search results"""
        soup = BeautifulSoup(html, 'html.parser')
        products = []

        # Try multiple selectors
        selectors = [
            "a[href*='/nav/achat/'][href*='.html']",
            ".product-card a",
            "[class*='product'] a[href*='/nav/achat/']",
        ]

        links = []
        for selector in selectors:
            links = soup.select(selector)
            if links:
                self.logger.info(f"Found {len(links)} products with selector: {selector}")
                break

        if not links:
            self.logger.warning("No products found on Darty")
            return []

        seen_urls = set()

        for link in links:
            try:
                href = link.get("href")
                if not href:
                    continue

                full_url = self.make_absolute_url(href)

                if full_url in seen_urls:
                    continue
                seen_urls.add(full_url)

                # Extract title
                title = link.get_text(strip=True)
                if not title:
                    title = link.get("title", "")

                # Try in parent
                if not title or len(title) < 3:
                    parent = link.find_parent(["article", "li", "div"])
                    if parent:
                        title_elem = parent.select_one("h2, h3, .product-title, [class*='title']")
                        if title_elem:
                            title = title_elem.get_text(strip=True)

                if not title or len(title) < 3:
                    continue

                # Filter by query
                if not self.filter_by_query(title, query):
                    continue

                # Extract image
                image_url = None
                parent = link.find_parent(["article", "li", "div"])
                if parent:
                    img_selectors = [
                        "img.product_img",
                        "img.product-image",
                        "img[class*='product']",
                        "img",
                    ]
                    for img_sel in img_selectors:
                        img = parent.select_one(img_sel)
                        if img:
                            image_url = self._get_image_src(img)
                            if image_url:
                                image_url = self.make_absolute_url(image_url)
                                break

                # Extract price
                price = None
                if parent:
                    price_selectors = [
                        ".price",
                        "[class*='price'][class*='current']",
                        "[data-testid='price']",
                        "span[class*='prix']",
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
                self.logger.error(f"Error parsing Darty product: {e}")
                continue

        self.logger.info(f"Extracted {len(products)} products from Darty")
        return products
