from bs4 import BeautifulSoup
from app.services.parsers.base_parser import BaseParser, ProductResult
import logging

logger = logging.getLogger(__name__)

class CarrefourParser(BaseParser):
    def __init__(self):
        super().__init__("carrefour.fr", "https://www.carrefour.fr")

    def parse_search_results(self, html: str, query: str, search_url: str) -> list[ProductResult]:
        soup = BeautifulSoup(html, "html.parser")
        results = []
        
        # Carrefour products
        # Config: a[href*='/p/']
        
        products = soup.select("article, div[class*='product-card']")
        
        for product in products:
            try:
                link_el = product.select_one("a[href*='/p/'], a[href*='/produit']")
                if not link_el:
                    continue
                    
                href = link_el.get('href')
                url = self.make_absolute_url(href)
                
                title_el = product.select_one("[class*='title'], h2, h3")
                title = title_el.get_text(strip=True) if title_el else link_el.get_text(strip=True)
                
                if not title:
                    continue

                img_url = self.extract_image_url(product)
                
                price = None
                price_el = product.select_one("[class*='price']")
                if price_el:
                    price = self.parse_price_text(price_el.get_text())
                
                results.append(ProductResult(
                    title=title,
                    url=url,
                    source="Carrefour",
                    price=price,
                    currency="EUR",
                    in_stock=True,
                    image_url=img_url,
                    snippet=f"Product from Carrefour"
                ))
                
            except Exception as e:
                logger.error(f"Error parsing Carrefour product: {e}")
                continue
                
        logger.info(f"CarrefourParser found {len(results)} results")
        return results
