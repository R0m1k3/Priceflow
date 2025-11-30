from bs4 import BeautifulSoup
from app.services.parsers.base_parser import BaseParser, ProductResult
import logging

logger = logging.getLogger(__name__)

class ActionParser(BaseParser):
    def __init__(self):
        super().__init__("action.com", "https://www.action.com")

    def parse_search_results(self, html: str, query: str, search_url: str) -> list[ProductResult]:
        soup = BeautifulSoup(html, "html.parser")
        results = []
        
        # Action products
        # Config: a.group[href^='/fr-fr/p/']
        
        links = soup.select("a[href^='/fr-fr/p/']")
        
        seen_urls = set()
        
        for link in links:
            try:
                href = link.get('href')
                if not href or href in seen_urls:
                    continue
                seen_urls.add(href)
                
                url = self.make_absolute_url(href)
                
                # Action usually has the card content inside the link
                title = None
                title_el = link.select_one("[class*='title'], h3, h4")
                if title_el:
                    title = title_el.get_text(strip=True)
                else:
                    title = link.get_text(strip=True)
                
                if not title:
                    continue

                img_url = self.extract_image_url(link)
                
                price = None
                price_el = link.select_one("[class*='price']")
                if price_el:
                    price = self.parse_price_text(price_el.get_text())
                
                results.append(ProductResult(
                    title=title,
                    url=url,
                    source="Action",
                    price=price,
                    currency="EUR",
                    in_stock=True,
                    image_url=img_url,
                    snippet=f"Product from Action"
                ))
                
            except Exception as e:
                logger.error(f"Error parsing Action product: {e}")
                continue
                
        logger.info(f"ActionParser found {len(results)} results")
        return results
