from bs4 import BeautifulSoup
from app.services.parsers.base_parser import BaseParser, ProductResult
import logging

logger = logging.getLogger(__name__)

class CdiscountParser(BaseParser):
    def __init__(self):
        super().__init__("cdiscount.com", "https://www.cdiscount.com")

    def parse_search_results(self, html: str, query: str, search_url: str) -> list[ProductResult]:
        soup = BeautifulSoup(html, "html.parser")
        results = []
        
        # Cdiscount products
        # Config: a.prdtBILnk, a[href*='/f-'][href*='.html']
        # We look for the card container or the link itself if it acts as a card
        
        # Try finding cards/links with new classes
        cards = soup.select("a[class*='sc-'], li.prdtBIL, div.prdtBIL, ul#lpBloc > li, div.js-prdt-bil")
        
        for card in cards:
            try:
                # Link
                if card.name == 'a':
                    link_el = card
                else:
                    link_el = card.select_one("a.prdtBILnk, a")
                
                if not link_el:
                    continue
                    
                href = link_el.get('href')
                if not href:
                    continue
                    
                url = self.make_absolute_url(href)
                
                # Title
                title = None
                title_el = card.select_one("h2, .prdtBTitle, .prdtBTit")
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
                price_el = card.select_one(".price, .prdtPrice, .prdtPInfo .price, span[class*='price']")
                if price_el:
                    price = self.parse_price_text(price_el.get_text())
                
                results.append(ProductResult(
                    title=title,
                    url=url,
                    source="Cdiscount",
                    price=price,
                    currency="EUR",
                    in_stock=True,
                    image_url=img_url,
                    snippet=f"Product from Cdiscount"
                ))
                
            except Exception as e:
                logger.error(f"Error parsing Cdiscount product: {e}")
                continue
                
        logger.info(f"CdiscountParser found {len(results)} results")
        return results
