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
        
        # Find product title links
        links = soup.select("a.reversed-link.block")
        
        seen_urls = set()
        
        for link in links:
            try:
                href = link.get('href')
                if not href or href in seen_urls:
                    continue
                
                if '/products/' not in href:
                    continue
                    
                seen_urls.add(href)
                url = self.make_absolute_url(href)
                
                title = link.get_text(strip=True)
                if not title:
                    continue

                # Image: Look for the preceding <a> with aria-label
                img_url = None
                prev_a = link.find_previous_sibling("a", attrs={"aria-label": True})
                if prev_a and prev_a.get('href') == href:
                    # Try specific selector first
                    img_el = prev_a.select_one("motion-element img, img")
                    if img_el:
                        img_url = self._get_image_src(img_el)
                    
                    if not img_url:
                        img_url = self.extract_image_url(prev_a)
                
                if img_url:
                    img_url = self.make_absolute_url(img_url)
                
                # Price: Look for text node after the link
                price = None
                next_sibling = link.next_sibling
                while next_sibling:
                    if isinstance(next_sibling, NavigableString):
                        price_text = next_sibling.strip()
                        if "€" in price_text:
                            price = self.parse_price_text(price_text)
                            if price:
                                break
                    elif next_sibling.name == 'div' and 'price' in str(next_sibling.get('class', [])):
                         # Try finding price in next div if it's a price container
                         price = self.parse_price_text(next_sibling.get_text())
                         if price:
                             break
                    next_sibling = next_sibling.next_sibling

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
