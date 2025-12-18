from bs4 import BeautifulSoup
from app.services.parsers.base_parser import BaseParser, ProductResult
import logging

logger = logging.getLogger(__name__)

class BMStoresParser(BaseParser):
    def __init__(self):
        super().__init__("bmstores.fr", "https://bmstores.fr")

    def parse_search_results(self, html: str, query: str, search_url: str) -> list[ProductResult]:
        soup = BeautifulSoup(html, "html.parser")
        results = []
        
        # B&M products
        # Config: a.thumbnail.product-thumbnail
        
        products = soup.select(".product-miniature, .js-product-miniature")
        
        for product in products:
            try:
                link_el = product.select_one("a.thumbnail.product-thumbnail")
                if not link_el:
                    continue
                    
                href = link_el.get('href')
                url = self.make_absolute_url(href)
                
                title_el = product.select_one(".product-title, h3")
                title = title_el.get_text(strip=True) if title_el else None
                
                if not title:
                    continue

                img_url = self.extract_image_url(product)
                
                price = None
                price_el = product.select_one(".product-price-and-shipping, .price")
                if price_el:
                    price = self.parse_price_text(price_el.get_text())
                
                results.append(ProductResult(
                    title=title,
                    url=url,
                    source="B&M",
                    price=price,
                    currency="EUR",
                    in_stock=True,
                    image_url=img_url,
                    snippet=f"Product from B&M"
                ))
                
            except Exception as e:
                logger.error(f"Error parsing B&M product: {e}")
                continue
                
        logger.info(f"BMStoresParser found {len(results)} results")
        return results

    def parse_product_details(self, html: str, product_url: str) -> dict:
        """
        Extract price and stock from B&M product page
        """
        soup = BeautifulSoup(html, "html.parser")
        details = {"price": None, "in_stock": True}
        
        # 1. Look for the main price (avoid suggested products prices)
        # B&M uses .current-price .price on detail pages
        price_el = soup.select_one(".product-prices .current-price .price, .product-price-and-shipping .price, [itemprop='price']")
        if price_el:
            details["price"] = self.parse_price_text(price_el.get_text())
            
        # 2. Check stock
        stock_text = soup.get_text().lower()
        if "épuisé" in stock_text or "indisponible" in stock_text:
            details["in_stock"] = False
            
        return details
