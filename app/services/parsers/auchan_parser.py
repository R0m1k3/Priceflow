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
        
        # Auchan products are usually in article or div with class product-item
        products = soup.select("article[class*='product-item'], div[class*='product-item']")
        
        for product in products:
            try:
                # Link and Title
                link_el = product.select_one("a[href*='/p-']")
                if not link_el:
                    continue
                    
                href = link_el.get('href')
                url = self.make_absolute_url(href)
                
                title = link_el.get('title') or link_el.get_text(strip=True)
                if not title:
                    continue

                # Image
                img_url = self.extract_image_url(product)
                
                # Price
                price = None
                price_el = product.select_one("span[class*='price__value'], div[class*='price--selling'], span[itemprop='price']")
                if price_el:
                    price = self.parse_price_text(price_el.get_text())
                
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
