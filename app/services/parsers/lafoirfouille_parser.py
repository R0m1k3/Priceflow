from bs4 import BeautifulSoup
from app.services.parsers.base_parser import BaseParser, ProductResult
import logging

logger = logging.getLogger(__name__)

class LaFoirFouilleParser(BaseParser):
    def __init__(self):
        super().__init__("lafoirfouille.fr", "https://www.lafoirfouille.fr")

    def parse_search_results(self, html: str, query: str, search_url: str) -> list[ProductResult]:
        soup = BeautifulSoup(html, "html.parser")
        results = []
        
        # La Foir'Fouille products
        # Config: article.product-miniature a.product-thumbnail
        
        products = soup.select("article.product-miniature")
        
        for product in products:
            try:
                link_el = product.select_one("a.product-thumbnail, a.product_img_link")
                if not link_el:
                    continue
                    
                href = link_el.get('href')
                url = self.make_absolute_url(href)
                
                title_el = product.select_one(".product-title, h3")
                title = title_el.get_text(strip=True) if title_el else None
                
                if not title:
                    continue

                img_url = self.extract_image_url(product)
                
                price = None
                price_el = product.select_one(".product-price-and-shipping, .price")
                if price_el:
                    price = self.parse_price_text(price_el.get_text())
                
                results.append(ProductResult(
                    title=title,
                    url=url,
                    source="La Foir'Fouille",
                    price=price,
                    currency="EUR",
                    in_stock=True,
                    image_url=img_url,
                    snippet=f"Product from La Foir'Fouille"
                ))
                
            except Exception as e:
                logger.error(f"Error parsing La Foir'Fouille product: {e}")
                continue
                
        logger.info(f"LaFoirFouilleParser found {len(results)} results")
        return results
