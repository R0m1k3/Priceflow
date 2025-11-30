from bs4 import BeautifulSoup
from app.services.parsers.base_parser import BaseParser, ProductResult
import logging

logger = logging.getLogger(__name__)

class StokomaniParser(BaseParser):
    def __init__(self):
        super().__init__("stokomani.fr", "https://www.stokomani.fr")

    def parse_search_results(self, html: str, query: str, search_url: str) -> list[ProductResult]:
        soup = BeautifulSoup(html, "html.parser")
        results = []
        
        # Find product cards
        # Based on inspection, links are a.reversed-link.block
        # We'll look for the container of these links
        links = soup.select("a.reversed-link.block, a[href*='/products/']")
        
        seen_urls = set()
        
        for link in links:
            try:
                href = link.get('href')
                if not href or href in seen_urls:
                    continue
                
                # Filter out non-product links
                if '/products/' not in href:
                    continue
                    
                seen_urls.add(href)
                url = self.make_absolute_url(href)
                
                # Title
                title = link.get_text(strip=True)
                if not title:
                    # Try finding title in nested elements
                    title_el = link.find(class_=lambda x: x and 'title' in x)
                    if title_el:
                        title = title_el.get_text(strip=True)
                
                if not title:
                    continue

                # Find parent card to scope image and price search
                # Usually the card is a few levels up
                card = link.find_parent("div", class_=lambda x: x and ("product" in x or "card" in x or "item" in x))
                if not card:
                    # Fallback: use the link's parent
                    card = link.parent.parent
                
                # Image
                img_url = self.extract_image_url(card)
                
                # Price
                price = None
                # Try specific price selectors first
                price_selectors = [
                    ".price", ".money", ".current-price", 
                    "span[class*='price']", "div[class*='price']"
                ]
                
                for selector in price_selectors:
                    price_el = card.select_one(selector)
                    if price_el:
                        price = self.parse_price_text(price_el.get_text())
                        if price:
                            break
                
                # Fallback: Look for price pattern in the card text
                if not price:
                    # Get text but exclude the title to avoid false positives if title has numbers
                    card_text = card.get_text(" ", strip=True)
                    price = self.parse_price_text(card_text)

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
