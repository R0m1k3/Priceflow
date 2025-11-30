from bs4 import BeautifulSoup
from app.services.parsers.base_parser import BaseParser, ProductResult
import logging
import re

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

                # Image - Robust extraction
                img_url = None
                
                # Exclude heart/wishlist icons explicitly
                # Select all images and filter
                images = card.select("img")
                valid_images = []
                for img in images:
                    src = img.get('src', '') or img.get('data-src', '')
                    classes = img.get('class', [])
                    
                    # Skip heart/wishlist icons
                    if 'coup2coeur' in str(classes).lower() or 'wishlist' in str(classes).lower():
                        continue
                    if 'coeur' in src.lower() or 'heart' in src.lower():
                        continue
                        
                    valid_images.append(img)
                
                # Prioritize product images
                for img in valid_images:
                    src = img.get('src', '') or img.get('data-src', '')
                    if 'product' in src.lower() or 'p/' in src.lower():
                        img_url = self._get_image_src(img)
                        break
                
                # Fallback to first valid image if no specific product image found
                if not img_url and valid_images:
                    img_url = self._get_image_src(valid_images[0])

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
                    # Look for price pattern: number followed by €
                    price_match = re.search(r'(\d+(?:[.,]\d+)?)\s*€', text)
                    if price_match:
                        price = self.parse_price_text(price_match.group(0))
                
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
