from bs4 import BeautifulSoup
from app.services.parsers.base_parser import BaseParser, ProductResult
import logging

logger = logging.getLogger(__name__)

class CentrakorParser(BaseParser):
    def __init__(self):
        super().__init__("centrakor.com", "https://www.centrakor.com")

    def parse_search_results(self, html: str, query: str, search_url: str) -> list[ProductResult]:
        soup = BeautifulSoup(html, "html.parser")
        results = []
        
        # Centrakor products
        # Config: a.link.link--block, a.product-item__link
        
        products = soup.select(".product-item, .product-card")
        
        for product in products:
            try:
                link_el = product.select_one("a.product-item__link, a.link")
                if not link_el:
                    continue
                    
                href = link_el.get('href')
                url = self.make_absolute_url(href)
                
                title_el = product.select_one(".product-item__name, .product-card__title")
                title = title_el.get_text(strip=True) if title_el else None
                
                if not title:
                    continue

                img_url = self.extract_image_url(product)
                
                price = None
                price_el = product.select_one(".price, .product-price")
                if price_el:
                    price = self.parse_price_text(price_el.get_text())
                
                results.append(ProductResult(
                    title=title,
                    url=url,
                    source="Centrakor",
                    price=price,
                    currency="EUR",
                    in_stock=True,
                    image_url=img_url,
                    snippet=f"Product from Centrakor"
                ))
                
            except Exception as e:
                logger.error(f"Error parsing Centrakor product: {e}")
                continue
                
        logger.info(f"CentrakorParser found {len(results)} results")
        return results
