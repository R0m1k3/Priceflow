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
        
        # Auchan products
        # Config: article, div[class*='product-card']
        
        cards = soup.select("article, div[class*='product-card'], div[class*='list__item']")
        
        # Fallback: try finding links directly
        if not cards:
            links = soup.select("a[href*='/p-']")
            cards = []
            for link in links:
                parent = link.find_parent("article") or link.find_parent("div", class_=lambda x: x and "product" in x)
                if parent:
                    cards.append(parent)
                else:
                    cards.append(link.parent)

        for card in cards:
            try:
                link_el = card.select_one("a[href*='/p-'], a")
                if not link_el:
                    continue
                    
                href = link_el.get('href')
                if not href or '/p-' not in href:
                    continue
                    
                url = self.make_absolute_url(href)
                
                title_el = card.select_one("h3, div[class*='title'], span[class*='title']")
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
                price_el = card.select_one("div[class*='price'], span[class*='price'], .product-price")
                if price_el:
                    price = self.parse_price_text(price_el.get_text())
                
                # Fallback price search in text
                if not price:
                    text = card.get_text(" ", strip=True)
                    price = self.parse_price_text(text)
                
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
