from bs4 import BeautifulSoup
from app.services.parsers.base_parser import BaseParser, ProductResult
import logging

logger = logging.getLogger(__name__)

class LIncroyableParser(BaseParser):
    def __init__(self):
        super().__init__("lincroyable.fr", "https://www.lincroyable.fr")

    def parse_search_results(self, html: str, query: str, search_url: str) -> list[ProductResult]:
        soup = BeautifulSoup(html, "html.parser")
        results = []
        
        # L'Incroyable products
        # Config: a.product-link
        
        products = soup.select(".product-card, .product-miniature")
        
        for product in products:
            try:
                link_el = product.select_one("a.product-link, a[href*='/p/']")
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
                price_el = product.select_one(".price, .product-price")
                if price_el:
                    price = self.parse_price_text(price_el.get_text())
                
                results.append(ProductResult(
                    title=title,
                    url=url,
                    source="L'Incroyable",
                    price=price,
                    currency="EUR",
                    in_stock=True,
                    image_url=img_url,
                    snippet=f"Product from L'Incroyable"
                ))
                
            except Exception as e:
                logger.error(f"Error parsing L'Incroyable product: {e}")
                continue
                
        logger.info(f"LIncroyableParser found {len(results)} results")
        return results
