from bs4 import BeautifulSoup
from app.services.parsers.base_parser import BaseParser, ProductResult
import logging

logger = logging.getLogger(__name__)

class GifiParser(BaseParser):
    def __init__(self):
        super().__init__("gifi.fr", "https://www.gifi.fr")

    def parse_search_results(self, html: str, query: str, search_url: str) -> list[ProductResult]:
        soup = BeautifulSoup(html, "html.parser")
        results = []
        
        # Gifi products
        # Config: a.link
        # Wait selector: .product-tile
        
        products = soup.select(".product-tile, div[class*='product-tile']")
        
        for product in products:
            try:
                link_el = product.select_one("a.link") or product.find("a")
                if not link_el:
                    continue
                    
                href = link_el.get('href')
                url = self.make_absolute_url(href)
                
                title = link_el.get_text(strip=True)
                if not title:
                    # Try finding title in nested elements
                    title_el = product.select_one("[class*='name'], [class*='title']")
                    if title_el:
                        title = title_el.get_text(strip=True)
                
                if not title:
                    continue

                img_url = self.extract_image_url(product)
                
                price = None
                price_el = product.select_one(".price, .value, [class*='price']")
                if price_el:
                    price = self.parse_price_text(price_el.get_text())
                
                results.append(ProductResult(
                    title=title,
                    url=url,
                    source="Gifi",
                    price=price,
                    currency="EUR",
                    in_stock=True,
                    image_url=img_url,
                    snippet=f"Product from Gifi"
                ))
                
            except Exception as e:
                logger.error(f"Error parsing Gifi product: {e}")
                continue
                
        logger.info(f"GifiParser found {len(results)} results")
        return results
