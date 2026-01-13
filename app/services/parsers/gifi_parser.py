from bs4 import BeautifulSoup
from app.services.parsers.base_parser import BaseParser, ProductResult
import logging

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

                href = link_el.get("href")
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
                    img_url = self.extract_image_url(
                        product, ["img.tile-image", "img[class*='product']", ".image-container img"]
                    )

                price = None
                # 1. Try specific price selectors
                price_el = product.select_one(".price, .value, [class*='price'], .sales .value")
                if price_el:
                    price = self.parse_price_text(price_el.get_text())

                # 2. Fallback: Use improved base logic on the entire product text
                if price is None:
                    product_text = product.get_text(separator=" ", strip=True)
                    price = self.parse_price_text(product_text)

                results.append(
                    ProductResult(
                        title=title,
                        url=url,
                        source="Gifi",
                        price=price,
                        currency="EUR",
                        in_stock=True,
                        image_url=img_url,
                        snippet=f"Product from Gifi",
                    )
                )

            except Exception as e:
                logger.error(f"Error parsing Gifi product: {e}")
                continue

        logger.info(f"GifiParser found {len(results)} results")
        return results

    def parse_product_details(self, html: str, product_url: str) -> dict:
        soup = BeautifulSoup(html, "html.parser")

        # 1. Price extraction
        price = None
        # Specific Gifi product page price selectors
        price_el = soup.select_one(".prices .price .value, .product-price .price .value, .price-sales .value")
        if price_el:
            price = self.parse_price_text(price_el.get_text())

        if price is None:
            # Fallback to schema.org data if present
            import json

            scripts = soup.find_all("script", type="application/ld+json")
            for script in scripts:
                if script.string:
                    try:
                        data = json.loads(script.string)
                        if isinstance(data, dict):
                            if data.get("@type") == "Product" and "offers" in data:
                                offers = data["offers"]
                                if isinstance(offers, list) and offers:
                                    offers = offers[0]
                                if "price" in offers:
                                    price = float(offers["price"])
                                    break
                            elif data.get("@type") == "Offer" and "price" in data:
                                price = float(data["price"])
                                break
                    except:
                        pass

        if price is None:
            # Text fallback using improved base logic
            price = self.parse_price_text(soup.get_text())

        # 2. Stock extraction
        in_stock = True  # specific availability check might be complex, default true if page loads

        # Check for "Out of stock" messages
        exhausted_el = soup.select_one(".availability-msg.exhausted, .availability-msg.out-of-stock")
        if exhausted_el:
            in_stock = False

        return {"price": price, "in_stock": in_stock, "currency": "EUR"}
