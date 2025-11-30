from bs4 import BeautifulSoup
from app.services.parsers.base_parser import BaseParser, ProductResult
import logging

logger = logging.getLogger(__name__)

class StokomaniParser(BaseParser):
    def __init__(self):
        super().__init__("stokomani.fr", "https://www.stokomani.fr")

    def parse_search_results(self, html: str, query: str, search_url: str) -> list[ProductResult]:
        from bs4 import BeautifulSoup, NavigableString
        soup = BeautifulSoup(html, "html.parser")
        results = []
        
        # Stokomani products
        # Config: div.product-card
        
        cards = soup.select("div.product-card")
        
        for card in cards:
            try:
                # Link
                link_el = card.select_one("h3.product-card__title a, a[href*='/products/']")
                if not link_el:
                    continue
                    
                href = link_el.get('href')
                url = self.make_absolute_url(href)
                
                # Title
                title_el = card.select_one("span.reversed-link__text, h3.product-card__title")
                title = title_el.get_text(strip=True) if title_el else link_el.get_text(strip=True)
                
                if not title:
                    continue

                # Image
                img_url = None
                img_el = card.select_one("div.media-wrapper img, img")
                if img_el:
                    img_url = self._get_image_src(img_el)
                    if img_url:
                        img_url = self.make_absolute_url(img_url)
                
                # Price
                price = None
                price_el = card.select_one("span.f-price-item--regular, .f-price-item, [class*='price']")
                if price_el:
                    price = self.parse_price_text(price_el.get_text())
                
                # Fallback price search in text
                if not price:
                    text = card.get_text(" ", strip=True)
                    price = self.parse_price_text(text)
                
                results.append(ProductResult(
                    title=title,
                    url=url,
                    source="Stokomani",
                    price=price,
                    currency="EUR",
                    in_stock=True,
                    image_url=img_url,
                    snippet=f"Product from Stokomani"
                ))
                
            except Exception as e:
                logger.error(f"Error parsing Stokomani product: {e}")
                continue
                
        logger.info(f"StokomaniParser found {len(results)} results")
        return results
