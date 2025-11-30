from bs4 import BeautifulSoup
from app.services.parsers.base_parser import BaseParser, ProductResult
import logging
import re

logger = logging.getLogger(__name__)

class GifiParser(BaseParser):
    def __init__(self):
        super().__init__("gifi.fr", "https://www.gifi.fr")

    def parse_search_results(self, html: str, query: str, search_url: str) -> list[ProductResult]:
        soup = BeautifulSoup(html, "html.parser")
        results = []
        
        # Gifi products
        # Config: a.link
        # Wait selector: .product-tile
        
        products = soup.select(".product-tile, div[class*='product-tile']")
        
        for product in products:
            try:
                link_el = product.select_one("a.link") or product.find("a")
                if not link_el:
                    continue
                    
                href = link_el.get('href')
                url = self.make_absolute_url(href)
                
                # Title: Try specific classes first to avoid getting rating text etc.
                title = None
                title_el = product.select_one(".pdp-link > a, .link, [class*='name'], [class*='title']")
                if title_el:
                    title = title_el.get_text(strip=True)
                
                if not title:
                    title = link_el.get_text(strip=True)
                
                if not title:
                    continue

                # Image extraction
                # Priority: picture img -> img with class -> any img
                img_url = None
                
                # 1. Try picture source (often high res)
                picture = product.select_one("picture")
                if picture:
                    source = picture.find("source")
                    if source and source.get("srcset"):
                        img_url = source.get("srcset").split(",")[0].split()[0]
                    
                    if not img_url:
                        img = picture.find("img")
                        if img:
                            img_url = self._get_image_src(img)
                
                # 2. Try direct image selectors
                if not img_url:
                    img_url = self.extract_image_url(product, [
                        "img.tile-image", 
                        "img[class*='product']", 
                        ".image-container img"
                    ])
                
                price = None
                # 1. Try specific price selectors
                price_el = product.select_one(".price, .value, [class*='price'], .sales .value")
                if price_el:
                    price = self.parse_price_text(price_el.get_text())
                
                # 2. Fallback: Regex on the entire product text
                if price is None:
                    product_text = product.get_text(separator=" ", strip=True)
                    # Look for price pattern: number followed by € or EUR
                    # e.g. "7,99 €", "12 €", "12.50€"
                    price_match = re.search(r'(\d+(?:[.,]\d+)?)\s*(?:€|EUR)', product_text, re.IGNORECASE)
                    if price_match:
                        price = self.parse_price_text(price_match.group(0))
                
                results.append(ProductResult(
                    title=title,
                    url=url,
                    source="Gifi",
                    price=price,
                    currency="EUR",
                    in_stock=True,
                    image_url=img_url,
                    snippet=f"Product from Gifi"
                ))
                
            except Exception as e:
                logger.error(f"Error parsing Gifi product: {e}")
                continue
                
        logger.info(f"GifiParser found {len(results)} results")
        return results
