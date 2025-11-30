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
        
        # Try finding cards first
        cards = soup.select("div.product-card, div.product-miniature, article")
        
        # If no cards found, try finding by link and getting parent
        if not cards:
            links = soup.select("a[href*='/p/'], a[href*='/produit/']")
            cards = []
            for link in links:
                # Try to find a container div
                parent = link.find_parent("div", class_=lambda x: x and ("product" in x or "card" in x))
                if parent:
                    cards.append(parent)
                else:
                    cards.append(link.parent) # Fallback to immediate parent

        for card in cards:
            try:
                link_el = card.select_one("a[href*='/p/'], a[href*='/produit/'], a.product-link")
                if not link_el:
                    # If card is the link itself
                    if card.name == 'a' and card.get('href'):
                        link_el = card
                    else:
                        continue
                    
                href = link_el.get('href')
                url = self.make_absolute_url(href)
                
                title_el = card.select_one(".product-title, h3, h2, [class*='title']")
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
                price_el = card.select_one(".price, .product-price, [class*='price']")
                if price_el:
                    price = self.parse_price_text(price_el.get_text())
                
                # Fallback price search in text
                if not price:
                    text = card.get_text(" ", strip=True)
                    price = self.parse_price_text(text)
                
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
