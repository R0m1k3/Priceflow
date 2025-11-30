from bs4 import BeautifulSoup
from app.services.parsers.base_parser import BaseParser, ProductResult
import logging

logger = logging.getLogger(__name__)

class ELeclercParser(BaseParser):
    def __init__(self):
        super().__init__("e-leclerc.com", "https://www.e.leclerc")

    def parse_search_results(self, html: str, query: str, search_url: str) -> list[ProductResult]:
        soup = BeautifulSoup(html, "html.parser")
        results = []
        
        # E.Leclerc products
        # Based on config: a.product-card-link
        # We look for the card container
        cards = soup.select("div[class*='product-card'], div[class*='product-item']")
        
        # If no cards found with div, try looking for the links directly and finding parents
        if not cards:
            links = soup.select("a.product-card-link")
            cards = [link.parent for link in links]

        for card in cards:
            try:
                # Link
                link_el = card.select_one("a.product-card-link") or card if card.name == 'a' else card.find('a')
                if not link_el:
                    continue
                    
                href = link_el.get('href')
                if not href:
                    continue
                    
                url = self.make_absolute_url(href)
                
                # Title
                title = None
                # Try specific title classes
                title_el = card.select_one("[class*='product-title'], [class*='product-label']")
                if title_el:
                    title = title_el.get_text(strip=True)
                else:
                    title = link_el.get_text(strip=True)
                
                if not title:
                    continue

                # Image
                img_url = self.extract_image_url(card)
                
                # Price
                price = None
                price_el = card.select_one("[class*='price'], [class*='amount']")
                if price_el:
                    price = self.parse_price_text(price_el.get_text())
                
                results.append(ProductResult(
                    title=title,
                    url=url,
                    source="E.Leclerc",
                    price=price,
                    currency="EUR",
                    in_stock=True,
                    image_url=img_url,
                    snippet=f"Product from E.Leclerc"
                ))
                
            except Exception as e:
                logger.error(f"Error parsing E.Leclerc product: {e}")
                continue
                
        logger.info(f"ELeclercParser found {len(results)} results")
        return results
