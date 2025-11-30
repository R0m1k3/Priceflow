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
        # Config: div.tailleBlocProdNew
        
        cards = soup.select("div.tailleBlocProdNew")
        
        for card in cards:
            try:
                # Link is usually in an 'a' tag inside, or the card itself might be clickable (but here we see multiple links)
                # We look for the main link to the product
                link_el = card.select_one("a[href*='/p']")
                if not link_el:
                    continue
                    
                href = link_el.get('href')
                url = self.make_absolute_url(href)
                
                # Title
                title_el = card.select_one("h3.nomCoupDeCoeurNew, .nomCoupDeCoeurNew")
                title = title_el.get_text(strip=True) if title_el else link_el.get_text(strip=True)
                
                if not title:
                    continue

                # Image
                img_url = None
                img_el = card.select_one("img.imgCoup2coeur, img")
                if img_el:
                    img_url = self._get_image_src(img_el)
                    if img_url:
                        img_url = self.make_absolute_url(img_url)
                
                # Price
                price = None
                price_el = card.select_one("p.prixCoupDeCoeurNew, .prixCoupDeCoeurNew")
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
