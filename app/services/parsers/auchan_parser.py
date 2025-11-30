from bs4 import BeautifulSoup
from app.services.parsers.base_parser import BaseParser, ProductResult
import logging

logger = logging.getLogger(__name__)

class AuchanParser(BaseParser):
    def __init__(self):
        super().__init__("auchan.fr", "https://www.auchan.fr")

    def parse_search_results(self, html: str, query: str, search_url: str) -> list[ProductResult]:
        soup = BeautifulSoup(html, "html.parser")
        results = []
        
        # Auchan products - Ultra Robust Strategy
        # The DOM is flat and dynamic. We rely on finding product links first.
        # Links usually contain '/p-' in the href.
        
        links = soup.select("a[href*='/p-']")
        seen_urls = set()
        
        for link in links:
            try:
                href = link.get('href')
                if not href or href in seen_urls:
                    continue
                
                # Filter out non-product links if any (e.g. facets)
                if '/p-' not in href:
                    continue
                    
                seen_urls.add(href)
                url = self.make_absolute_url(href)
                
                # Find the container: usually the link itself or a close parent
                # We look for a parent that contains price or image info
                container = link
                for _ in range(5): # Go up 5 levels max
                    parent = container.parent
                    if not parent:
                        break
                    container = parent
                    # Stop if we hit a large container or list item
                    if container.name == 'article' or (container.get('class') and any('list__item' in c for c in container.get('class'))):
                        break
                    # Stop if we find a price element inside this container that isn't the link itself
                    if container.select_one("span[class*='price'], div[class*='price']"):
                        break
                
                # Title
                title = link.get('title')
                if not title:
                    title_el = container.select_one("h3, div[class*='title'], span[class*='title']")
                    if title_el:
                        title = title_el.get_text(strip=True)
                if not title:
                    title = link.get_text(strip=True)
                
                if not title:
                    continue

                # Image
                img_url = None
                img_el = container.select_one("img")
                if img_el:
                    img_url = self._get_image_src(img_el)
                    if img_url:
                        img_url = self.make_absolute_url(img_url)
                
                # Price
                price = None
                price_el = container.select_one("div[class*='price'], span[class*='price'], .product-price")
                if price_el:
                    price = self.parse_price_text(price_el.get_text())
                
                # Fallback price search in text of container
                if not price:
                    text = container.get_text(" ", strip=True)
                    price = self.parse_price_text(text)
                
                results.append(ProductResult(
                    title=title,
                    url=url,
                    source="Auchan",
                    price=price,
                    currency="EUR",
                    in_stock=True,
                    image_url=img_url,
                    snippet=f"Product from Auchan"
                ))
                
            except Exception as e:
                logger.error(f"Error parsing Auchan product: {e}")
                continue
                
        logger.info(f"AuchanParser found {len(results)} results")
        return results
