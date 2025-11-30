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
        # New container: div containing both image and title link
        cards = soup.select("div.product-list-card-plp-grid-new, article, div[class*='product-card']") 
        
        # If no cards, try finding by link
        if not cards:
            links = soup.select("a.c-link.product-card-click-wrapper, a[href*='/p/'], a[href*='/produit']")
            cards = []
            for link in links:
                parent = link.find_parent("div", class_=lambda x: x and "product" in x)
                if parent:
                    cards.append(parent)
                else:
                    cards.append(link.parent.parent)

        for card in cards:
            try:
                link_el = card.select_one("a.c-link.product-card-click-wrapper, a[href*='/p/'], a[href*='/produit']")
                if not link_el:
                    continue
                    
                href = link_el.get('href')
                url = self.make_absolute_url(href)
                
                title_el = card.select_one("h3, h2, [class*='title']")
                title = title_el.get_text(strip=True) if title_el else link_el.get_text(strip=True)
                
                if not title:
                    continue

                img_url = None
                img_el = card.select_one("img")
                if img_el:
                    img_url = self._get_image_src(img_el)
                    if img_url:
                        img_url = self.make_absolute_url(img_url)
                
                price = None
                # Price is often text node near h3 or in a specific price element
                price_el = card.select_one("[class*='price'], .product-card-price, span[class*='amount']")
                if price_el:
                    price = self.parse_price_text(price_el.get_text())
                
                if not price:
                    # Fallback: check all text in the card for a price pattern
                    text = card.get_text(" ", strip=True)
                    # Simple regex for price like 12,99 € or 12.99€
                    import re
                    match = re.search(r'(\d+[.,]\d{2})\s*€?', text)
                    if match:
                        price = self.parse_price_text(match.group(0))
                
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
